-- Name and address cleaning rules: the single source of truth.
-- Used by the pipeline (persistent macros in the warehouse) and by the API on GC input
-- (installed as TEMP macros on a read-only connection), so build-time and query-time cleaning can't drift.
--
-- Principle: only remove noise that never distinguishes two companies (case, punctuation, legal form,
-- per-inspection ID prefixes). Never remove trade words, initials, numbers or place words here.
-- Each step is its own macro so the build can report how many names each rule merges.

-- n1: uppercase, unicode-normalise, collapse whitespace
CREATE OR REPLACE MACRO ssi_n1_upper(s) AS
  trim(regexp_replace(upper(nfc_normalize(coalesce(s, ''))), '\s+', ' ', 'g'));

-- n2: strip per-inspection ID prefixes ("WA317965935 - ", "105314 - "); needs 3+ digits AND a dash,
-- so "84 LUMBER" and "1ST CHOICE ROOFING" are untouched
CREATE OR REPLACE MACRO ssi_n2_strip_id(s) AS
  regexp_replace(s, '^[A-Z]{0,3}[0-9]{3,}\s*-\s*', '');

-- n3: delete apostrophes and periods without a space (L.L.C. -> LLC, O'BRIEN -> OBRIEN, J.R. -> JR)
CREATE OR REPLACE MACRO ssi_n3_dots(s) AS
  regexp_replace(s, '[''’.`]', '', 'g');

-- n4: canonical DBA marker (D/B/A, D B A, DBA, DOING BUSINESS AS, T/A, TRADING AS, A/K/A, AKA)
CREATE OR REPLACE MACRO ssi_n4_dba(s) AS
  regexp_replace(s, '\s*\b(D\s*/?\s*B\s*/?\s*A|DOING BUSINESS AS|T\s*/\s*A|TRADING AS|A\s*/?\s*K\s*/?\s*A)\b\s*', ' DBA ', 'g');

-- n5: trailing state-of-incorporation note, e.g. "(DELAWARE)", "(TX)"
CREATE OR REPLACE MACRO ssi_n5_state_note(s) AS
  regexp_replace(s, '\s*\((ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW HAMPSHIRE|NEW JERSEY|NEW MEXICO|NEW YORK|NORTH CAROLINA|NORTH DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE ISLAND|SOUTH CAROLINA|SOUTH DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST VIRGINIA|WISCONSIN|WYOMING|[A-Z]{2})\)\s*$', '');

-- n6: every other non-alphanumeric character (& + - / , ( ) …) becomes a space; then drop the word AND
--     so "BRASFIELD & GORRIE" = "BRASFIELD - GORRIE" = "BRASFIELD AND GORRIE" = "BRASFIELD GORRIE"
CREATE OR REPLACE MACRO ssi_n6_separators(s) AS
  trim(regexp_replace(regexp_replace(regexp_replace(s, '[^A-Z0-9 ]', ' ', 'g'), '\bAND\b', ' ', 'g'), '\s+', ' ', 'g'));

-- n7: drop a leading THE
CREATE OR REPLACE MACRO ssi_n7_the(s) AS
  regexp_replace(s, '^THE\s+', '');

-- n8: join spaced-out legal forms (L L C -> LLC, L P -> LP, G P -> GP, P L L C -> PLLC, L L P -> LLP)
CREATE OR REPLACE MACRO ssi_n8_join_legal(s) AS
  regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(s,
    '\bP L L C\b', 'PLLC', 'g'), '\bL L C\b', 'LLC', 'g'), '\bL L P\b', 'LLP', 'g'), '\bL P\b', 'LP', 'g'), '\bG P\b', 'GP', 'g');

-- n9: strip legal forms ONLY at the end of the name, and at the end of the legal name before a DBA.
--     Never strips a name down to nothing.
CREATE OR REPLACE MACRO ssi_n9_legal_core(s) AS
  trim(regexp_replace(regexp_replace(s,
    '(\s+(INC|INCORPORATED|LLC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|GP|PLLC|PC))+\s+DBA\b', ' DBA', 'g'),
    '(\s+(INC|INCORPORATED|LLC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|GP|PLLC|PC))+\s*$', ''));
CREATE OR REPLACE MACRO ssi_n9_legal(s) AS
  CASE WHEN ssi_n9_legal_core(s) = '' THEN s ELSE ssi_n9_legal_core(s) END;

-- n10: join runs of single letters (J R JOHNSON -> JR JOHNSON, M M MASONRY -> MM MASONRY).
--      Single letters are marked first so a run of any length up to 5 joins consistently.
CREATE OR REPLACE MACRO ssi_n10_mark_singles(s) AS
  array_to_string(list_transform(string_split(s, ' '),
    lambda t: CASE WHEN regexp_full_match(t, '[A-Z]') THEN t || '§' ELSE t END), ' ');
CREATE OR REPLACE MACRO ssi_n10_initials(s) AS
  replace(
    regexp_replace(regexp_replace(regexp_replace(regexp_replace(ssi_n10_mark_singles(s),
      '§ ([A-Z]§)', '\1', 'g'), '§ ([A-Z]§)', '\1', 'g'), '§ ([A-Z]§)', '\1', 'g'), '§ ([A-Z]§)', '\1', 'g'),
    '§', '');

-- The full name rule, in order. clean_name() is what establishment keys and matching use.
CREATE OR REPLACE MACRO clean_name(s) AS
  trim(regexp_replace(
    ssi_n10_initials(ssi_n9_legal(ssi_n8_join_legal(ssi_n7_the(ssi_n6_separators(
      ssi_n5_state_note(ssi_n4_dba(ssi_n3_dots(ssi_n2_strip_id(ssi_n1_upper(s)))))))))),
  '\s+', ' ', 'g'));

-- Legal name and trade name of a "X DBA Y" string (both become searchable aliases)
CREATE OR REPLACE MACRO legal_part(clean) AS trim(split_part(clean, ' DBA ', 1));
CREATE OR REPLACE MACRO dba_part(clean) AS
  CASE WHEN strpos(clean, ' DBA ') > 0 THEN nullif(trim(split_part(clean, ' DBA ', 2)), '') END;

-- Placeholders: inspectors' stand-ins for an unidentified employer. Never matchable.
CREATE OR REPLACE MACRO is_placeholder(clean) AS
  coalesce(clean, '') = ''
  OR regexp_matches(clean, '\b(UNKNOWN|UNKOWN|UNKNWN|UNIDENTIFIED)\b|INVALID ESTABLISHMENT')
  OR regexp_full_match(clean, 'N ?A|NONE|TBD|NO NAME|TEST|NOT AVAILABLE|VARIOUS|OWNER');

-- Joint ventures are flagged and linked to members, never merged into them
CREATE OR REPLACE MACRO is_jv(clean) AS regexp_matches(clean, '\b(JV|JOINT VENTURE)\b');

-- Sibling-entity suffix: "... OF OREGON", "... AT MERIDIAN" (evaluation found these are usually separate companies)
CREATE OR REPLACE MACRO sibling_suffix(clean) AS
  nullif(regexp_extract(clean, '\s(OF|AT)\s+([A-Z0-9 ]+)$', 0), '');

-- Name core: the cleaned name minus generic trade/descriptor words. Used to spot lookalikes and to
-- measure how distinctive a name is. Generic words were picked from the most frequent tokens in
-- construction names (see docs); personal names and place words are deliberately NOT generic.
CREATE OR REPLACE MACRO ssi_generic_tokens() AS [
  'OF','DE','DBA','AT','A','N',
  'CONSTRUCTION','CONSTRUCTORS','CONTRACTING','CONTRACTORS','CONTRACTOR','BUILDERS','BUILDER','BUILDING','BUILD',
  'ROOFING','ROOF','ROOFERS','SERVICES','SERVICE','GROUP','MASONRY','PAINTING','PAINTERS','FRAMING','CONCRETE',
  'HOME','HOMES','PLUMBING','GENERAL','DEVELOPMENT','ENTERPRISES','ENTERPRISE','MECHANICAL','REMODELING','SOLUTIONS',
  'HEATING','DRYWALL','SYSTEMS','SYSTEM','EXCAVATING','EXCAVATION','ELECTRIC','ELECTRICAL','SIDING','CARPENTRY',
  'STEEL','RESTORATION','EXTERIORS','EXTERIOR','INTERIORS','INTERIOR','CUSTOM','DESIGN','METAL','METALS','WORKS',
  'AIR','MANAGEMENT','IMPROVEMENT','IMPROVEMENTS','ASSOCIATES','COMMERCIAL','RESIDENTIAL','GLASS','STUCCO',
  'MAINTENANCE','INDUSTRIAL','INDUSTRIES','STONE','SHEET','PLASTERING','ENGINEERING','ERECTORS','ENERGY',
  'CONDITIONING','PAVING','INSULATION','PROPERTIES','PROPERTY','COMPANIES','CRANE','CRANES','RIGGING','TILE',
  'FIRE','FLOORING','FLOORS','POWER','COOLING','WELDING','SOLAR','DEMOLITION','RENOVATIONS','RENOVATION','WATER',
  'TECH','REPAIR','REPAIRS','ENVIRONMENTAL','HVAC','LANDSCAPING','LANDSCAPE','CABINETS','DOORS','WINDOWS','FENCE',
  'FENCING','GUTTERS','GUTTER','SEAMLESS','SPRINKLER','PROTECTION','SAFETY','UTILITIES','UTILITY','PIPELINE',
  'DRILLING','BORING','TRUCKING','HAULING','GRADING','SITE','SITEWORK','MARINE','HOLDINGS','INSTALLATION',
  'INSTALLATIONS','BROTHERS','BROS','SONS','SON','QUALITY','PRO','PROS','PROFESSIONAL','PROFESSIONALS','PREMIER',
  'PREMIUM','BEST','ALL','ADVANCED','SUPERIOR','ELITE','TOTAL','COMPLETE','UNITED','NATIONAL','AMERICAN','USA',
  'CO','INC','LLC','CORP','COMPANY','LTD','LP','LLP','GP','PLLC','PC'
];
CREATE OR REPLACE MACRO name_core(clean) AS
  coalesce(array_to_string(list_filter(string_split(legal_part(clean), ' '),
    lambda t: t <> '' AND NOT list_contains(ssi_generic_tokens(), t)), ' '), '');
CREATE OR REPLACE MACRO initials_only(clean) AS
  name_core(clean) <> '' AND
  len(list_filter(string_split(name_core(clean), ' '), lambda t: length(t) > 3)) = 0
  AND regexp_full_match(name_core(clean), '[A-Z]{1,3}( [A-Z]{1,3})*');

-- Addresses ------------------------------------------------------------------------------------
-- USPS abbreviations and directionals (WEST left alone: often a street name)
CREATE OR REPLACE MACRO clean_addr(s) AS trim(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(
   regexp_replace(upper(coalesce(s, '')), '[^A-Z0-9 ]', ' ', 'g'),
   '\b(P O|POST OFFICE|P0)\s+BOX\b', 'PO BOX', 'g'),
   '\bSTREET\b', 'ST', 'g'), '\bAVENUE\b', 'AVE', 'g'), '\bROAD\b', 'RD', 'g'), '\bDRIVE\b', 'DR', 'g'),
   '\bBOULEVARD\b', 'BLVD', 'g'), '\bSUITE\b', 'STE', 'g'), '\bHIGHWAY\b', 'HWY', 'g'), '\bPARKWAY\b', 'PKWY', 'g'),
   '\bLANE\b', 'LN', 'g'), '\bCOURT\b', 'CT', 'g'), '\bPLACE\b', 'PL', 'g'), '\bCIRCLE\b', 'CIR', 'g'),
   '\bNORTH\b', 'N', 'g'), '\bSOUTH\b', 'S', 'g'), '\bEAST\b', 'E', 'g'),
 '\s+', ' ', 'g'));

-- Unit (suite, floor, #) kept separately so "1201 DEMONBREUN ST" and "... STE 200" are the same building
CREATE OR REPLACE MACRO addr_unit(s) AS
  nullif(regexp_extract(upper(coalesce(s, '')), '\b(STE|SUITE|UNIT|APT|FL|FLOOR|RM|ROOM|BLDG|#)\s*#?\s*([A-Z0-9-]+)\s*$', 0), '');

-- Address key: house number + first street word (skipping a leading directional), or "POBOX <n>".
-- Tolerates suffix variants ("7TH AVE SOUTH" = "7TH AVE S") and suites.
CREATE OR REPLACE MACRO addr_key(s) AS CASE
  WHEN regexp_matches(clean_addr(s), '\bPO BOX\s+[0-9]+') THEN 'POBOX ' || regexp_extract(clean_addr(s), '\bPO BOX\s+([0-9]+)', 1)
  WHEN regexp_matches(clean_addr(s), '^[0-9]+[A-Z]?\s+') THEN
       regexp_extract(clean_addr(s), '^([0-9]+)[A-Z]?\s+(?:(?:N|S|E|W|WEST|NE|NW|SE|SW)\s+)?([A-Z0-9]+)', 1) || ' ' ||
       regexp_extract(clean_addr(s), '^([0-9]+)[A-Z]?\s+(?:(?:N|S|E|W|WEST|NE|NW|SE|SW)\s+)?([A-Z0-9]+)', 2)
  ELSE NULL END;

CREATE OR REPLACE MACRO zip5(z) AS CASE
  WHEN regexp_matches(trim(coalesce(z, '')), '^[0-9]{5}') AND substr(trim(z), 1, 5) <> '00000' THEN substr(trim(z), 1, 5)
  WHEN regexp_full_match(trim(coalesce(z, '')), '[0-9]{4}') THEN '0' || trim(z)
  ELSE NULL END;

-- Establishment key: stable across rebuilds (same cleaned inputs -> same key)
CREATE OR REPLACE MACRO establishment_key(clean, akey, z5, st) AS
  md5(coalesce(clean, '') || '|' || coalesce(akey, '') || '|' || coalesce(z5, '') || '|' || coalesce(st, ''));
