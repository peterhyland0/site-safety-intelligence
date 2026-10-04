-- Name and address cleaning rules: the single source of truth.
-- Used by the pipeline (persistent macros in the warehouse) and by the API on GC input
-- (installed as TEMP macros on a read-only connection), so build-time and query-time cleaning can't drift.
--
-- Principle: only remove noise that never distinguishes two companies (case, punctuation, legal form,
-- per-inspection ID prefixes). Never remove trade words, initials, numbers or place words here.
-- Each step is its own macro so the build can report how many names each rule merges.

-- n1: uppercase, unicode-normalise, fold accents (MUÑOZ -> MUNOZ: OSHA's names are typed without them, and
--     n6 would otherwise cut "MU OZ"), collapse whitespace. Letters strip_accents leaves are spelled out
--     (Ø Ł Đ Ð Þ Æ Œ ß). OSHA's own lost accents ("BERM?DEZ", "BERM�DEZ": two markers for one company) stay
--     punctuation, so both still clean to BERM DEZ. A name pasted from a PDF can carry ligatures (ﬁ ﬂ) or
--     full-width letters; DuckDB has no NFKC, so they are folded here (n6 would otherwise delete them:
--     "ﬂoor" -> "OOR").
CREATE OR REPLACE MACRO ssi_n1_upper(s) AS
  trim(regexp_replace(
    replace(replace(replace(replace(translate(upper(strip_accents(nfc_normalize(
      replace(replace(replace(replace(replace(translate(coalesce(s, ''),
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９＆',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&'),
        'ﬃ', 'ffi'), 'ﬄ', 'ffl'), 'ﬀ', 'ff'), 'ﬁ', 'fi'), 'ﬂ', 'fl')))), 'ØŁĐÐ', 'OLDD'),
      'Æ', 'AE'), 'Œ', 'OE'), 'ẞ', 'SS'), 'Þ', 'TH'),
    '\s+', ' ', 'g'));

-- n2: strip per-inspection ID prefixes ("WA317965935 - ", "105314 - ", "1234 - "): 5+ digits and a dash,
-- or 3+ digits and a spaced dash. Also the case numbers Arizona (since 2021: "FCX2024XEG419X0079 - ") and
-- Iowa (since 2026: "A09CS000013UQXVAA4 - ") put in front of the name: letters, a digit, 8+ more letters
-- or digits with 4+ digits in all (the build check's test), a spaced dash. "84 LUMBER", "1ST CHOICE ROOFING",
-- "561-ROOFING" (a company number) and "START2FINISHNJ - ROOFING" (a name with one digit) are untouched.
-- (A macro's argument is pasted in wherever it is used, so a step that needs its input twice takes it through a
-- lambda: written out three times, each step multiplies the size of every step before it.)
CREATE OR REPLACE MACRO ssi_n2_strip_id(s) AS
  list_transform([s], lambda x:
    CASE WHEN regexp_matches(x, '^[A-Z]+[0-9][A-Z0-9]{8,}\s+-\s+')
              AND length(regexp_replace(split_part(x, ' ', 1), '[^0-9]', '', 'g')) >= 4
         THEN regexp_replace(x, '^[A-Z]+[0-9][A-Z0-9]{8,}\s+-\s+', '')
         ELSE regexp_replace(x, '^[A-Z]{0,3}([0-9]{5,}\s*-\s*|[0-9]{3,}\s+-\s+)', '') END)[1];

-- n3: delete apostrophes and periods without a space (L.L.C. -> LLC, O'BRIEN -> OBRIEN, J.R. -> JR). Every
--     apostrophe a keyboard or word processor makes counts (' ’ ‘ ` ´ ʼ): "O´BRIEN" was "O BRIEN".
CREATE OR REPLACE MACRO ssi_n3_dots(s) AS
  regexp_replace(s, '[''’‘`´ʼ.]', '', 'g');

-- n4: canonical DBA marker (D/B/A, D B A, DBA, DOING BUSINESS AS, T/A, TRADING AS, A/K/A, AKA) after a name.
--     A name that starts with one keeps it: AKA ELECTRIC and A.K.A. CONSTRUCTION are companies called AKA
--     (they were "DBA ELECTRIC", a name with no core).
CREATE OR REPLACE MACRO ssi_n4_dba(s) AS
  regexp_replace(s, '(\S)\s*\b(D\s*/?\s*B\s*/?\s*A|DOING BUSINESS AS|T\s*/\s*A|TRADING AS|A\s*/?\s*K\s*/?\s*A)\b\s*', '\1 DBA ', 'g');

-- n5: trailing state-of-incorporation note, e.g. "(DELAWARE)", "(TX)". Not "(JV)": a joint venture is
--     its own company and must stay flagged as one (is_jv), never merged into a member.
CREATE OR REPLACE MACRO ssi_n5_state_note(s) AS
  regexp_replace(regexp_replace(s, '\(\s*JV\s*\)\s*$', ' JV'), '\s*\((ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW HAMPSHIRE|NEW JERSEY|NEW MEXICO|NEW YORK|NORTH CAROLINA|NORTH DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE ISLAND|SOUTH CAROLINA|SOUTH DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST VIRGINIA|WISCONSIN|WYOMING|[A-Z]{2})\)\s*$', '');

-- n6: every other non-alphanumeric character (& + - / , ( ) …) becomes a space; then drop the word AND
--     so "BRASFIELD & GORRIE" = "BRASFIELD - GORRIE" = "BRASFIELD AND GORRIE" = "BRASFIELD GORRIE"
CREATE OR REPLACE MACRO ssi_n6_separators(s) AS
  trim(regexp_replace(regexp_replace(regexp_replace(s, '[^A-Z0-9 ]', ' ', 'g'), '\bAND\b', ' ', 'g'), '\s+', ' ', 'g'));

-- n7: drop a leading THE, and a trailing one ("CLARK CONSTRUCTION GROUP LLC THE" is how some offices
--     write "The Clark Construction Group, LLC")
CREATE OR REPLACE MACRO ssi_n7_the(s) AS
  regexp_replace(regexp_replace(s, '^THE\s+', ''), '\s+THE$', '');

-- n8: join spaced-out legal forms (L L C -> LLC, L P -> LP, G P -> GP, P L L C -> PLLC, L L P -> LLP).
--     L P and G P only after a word, not after another single letter: in "R G P INC" and "J L P CONSTRUCTION"
--     they are initials (RGP, JLP); joining them first left "R GP INC", which n9 cut down to "R".
CREATE OR REPLACE MACRO ssi_n8_join_legal(s) AS
  regexp_replace(regexp_replace(regexp_replace(regexp_replace(s,
    '\bP L L C\b', 'PLLC', 'g'), '\bL L C\b', 'LLC', 'g'), '\bL L P\b', 'LLP', 'g'), '(^|[A-Z0-9]{2,} )([LG]) P\b', '\1\2P', 'g');

-- n9: strip legal forms ONLY at the end of the name, and at the end of the legal name before a DBA.
--     Never strips a name down to nothing. Besides the usual forms: Iowa's and Virginia's L.C., LLLP, PLC,
--     the spelt-out LIMITED LIABILITY COMPANY, the LCC slip, CO.INC, and the cut-off INCORPORA… / CORPORATIO…
--     of names that hit a field's length limit (each was a second establishment of the same company, and
--     "ADELPHI CONSTRUCTION LC" was excluded as a different name, LC, from ADELPHI CONSTRUCTION).
--     A THE between the name and its legal form goes too ("ANDREWS GROUP THE LLC"), and so does a DBA
--     with nothing after it ("CRAIG HANES, INC, DBA").
CREATE OR REPLACE MACRO ssi_n9_legal_core(s) AS
  trim(regexp_replace(regexp_replace(regexp_replace(s, '\s+DBA$', ''),
    '(\s+(INC|INCORPORATED|INCORPORATION|INCORPORATE|INCORPORAT|INCORPORA|INCORPOR|INCORP|LLC|LCC|LC|CORP|CORPORATION|CORPORATIO|CORPORATI|CORPORAT|CO|COINC|COMPANY|LTD|LIMITED LIABILITY|LIMITED|LP|LLP|LLLP|GP|PLLC|PLC|PC))+\s+DBA\b', ' DBA', 'g'),
    '(\s+(THE|INC|INCORPORATED|INCORPORATION|INCORPORATE|INCORPORAT|INCORPORA|INCORPOR|INCORP|LLC|LCC|LC|CORP|CORPORATION|CORPORATIO|CORPORATI|CORPORAT|CO|COINC|COMPANY|LTD|LIMITED LIABILITY|LIMITED|LP|LLP|LLLP|GP|PLLC|PLC|PC))+\s*$', ''));
CREATE OR REPLACE MACRO ssi_n9_legal(s) AS
  list_transform([s], lambda x: coalesce(nullif(ssi_n9_legal_core(x), ''), x))[1];

-- n10: join runs of single letters of any length (J R JOHNSON -> JR JOHNSON, H V A C -> HVAC), the way the
--      dotted spelling (H.V.A.C.) already joins in n3. Each single letter is wrapped in markers and the marks
--      between two neighbours are deleted in one pass (pairwise joining left "A B C D" as "AB CD").
--      Then a single letter and a number join (A-1 ROOFING = A 1 ROOFING = A1 ROOFING, D-7 = D7).
CREATE OR REPLACE MACRO ssi_n10_mark_singles(s) AS
  array_to_string(list_transform(string_split(s, ' '),
    lambda t: CASE WHEN regexp_full_match(t, '[A-Z]') THEN '¶' || t || '§' ELSE t END), ' ');
CREATE OR REPLACE MACRO ssi_n10_initials(s) AS
  regexp_replace(
    replace(replace(replace(ssi_n10_mark_singles(s), '§ ¶', ''), '¶', ''), '§', ''),
    '(^| )([A-Z]) ([0-9]{1,3})( |$)', '\1\2\3\4', 'g');

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

-- Placeholders: inspectors' stand-ins for an unidentified employer, and OSHA's own offices entered as the
-- employer on internal records ("USDOL OSHA CINCINNATI AREA OFFICE": no inspection, no citations). Never matchable.
CREATE OR REPLACE MACRO is_placeholder(clean) AS
  coalesce(clean, '') = ''
  OR regexp_matches(clean, '\b(UNKNOWN|UNKOWN|UNKNWN|UNIDENTIFIED)\b|INVALID ESTABLISHMENT')
  OR regexp_full_match(clean, 'N ?A|NONE|TBD|NO NAME|TEST|NOT AVAILABLE|VARIOUS|OWNER|UNK|HOME ?OWNERS?|ROOFER|'
                              || 'ROOFING CONTRACTOR|CONTRACTOR|SELF EMPLOYED')
  OR regexp_matches(clean, '^(US ?DOL|USDL|US DEPARTMENT OF LABOR|US DEPT OF LABOR|DEPARTMENT OF LABOR|DOL) OSHA\b|^OSHA$'
                           || '|^OSHA( [A-Z]+)* (AREA|DISTRICT|REGIONAL) OFFICE$|\bAREA OSHA OFFICE$');

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
-- Descriptor words: generic words that do NOT signal a different line of business. Two names with the
-- same core that differ only by these (BRASFIELD GORRIE vs BRASFIELD GORRIE GENERAL CONTRACTOR) are the same
-- company; names that differ by a TRADE word (WAUSAU HOMES vs WAUSAU TILE) are usually sister companies.
CREATE OR REPLACE MACRO ssi_descriptor_tokens() AS [
  'OF','DE','DBA','AT','A','N','GENERAL','CONTRACTOR','CONTRACTORS','CONTRACTING','CONSTRUCTION','CONSTRUCTORS',
  'SERVICES','SERVICE','GROUP','ENTERPRISES','ENTERPRISE','COMPANIES','HOLDINGS','ASSOCIATES','INDUSTRIES',
  'SOLUTIONS','MANAGEMENT','BROTHERS','BROS','SONS','SON','UNITED','NATIONAL','AMERICAN','USA','TOTAL','COMPLETE',
  'CO','INC','LLC','CORP','COMPANY','LTD','LP','LLP','GP','PLLC','PC'
];
CREATE OR REPLACE MACRO name_core(clean) AS
  coalesce(array_to_string(list_filter(string_split(legal_part(clean), ' '),
    lambda t: t <> '' AND NOT list_contains(ssi_generic_tokens(), t)), ' '), '');
CREATE OR REPLACE MACRO initials_only(clean) AS
  name_core(clean) <> '' AND
  len(list_filter(string_split(name_core(clean), ' '), lambda t: length(t) > 3)) = 0
  AND regexp_full_match(name_core(clean), '[A-Z]{1,3}( [A-Z]{1,3})*');

-- A person's name (sole proprietors appear in OSHA's data under the owner's name, and the same name is usually
-- many different people). A core of 2-4 plain words that is:
--   a given name first (JUAN GARCIA, JOSE A HERNANDEZ -> JOSE HERNANDEZ);
--   surname first, then a given name (HERNANDEZ JOSE), or a given name and a middle initial (MORALES JAVIER M),
--     unless the first word starts a place name (SAN ANTONIO, ST GEORGE, FORT WAYNE are companies' names);
--   an initial and a common surname (J LOPEZ: 8 records in 7 states, rated distinctive before).
-- `given` and `surnames` are the lists in ref/given_name.csv and ref/surname.csv. Mirrors
-- ssi.matching.candidates.is_person_core, which rates the GC's own entry at query time.
CREATE OR REPLACE MACRO ssi_place_prefixes() AS [
  'SAN','SANTA','SANTO','ST','SAINT','FORT','FT','MOUNT','MT','PORT','LOS','LAS','LAKE','CAPE'
];
CREATE OR REPLACE MACRO ssi_person_tokens(tok, given, surnames) AS
  (list_contains(given, tok[1])
   OR (NOT list_contains(ssi_place_prefixes(), tok[1]) AND list_contains(given, tok[2])
       AND (len(tok) = 2 OR (len(tok) = 3 AND length(tok[3]) = 1)))
   OR (len(tok) = 2 AND length(tok[1]) = 1 AND list_contains(surnames, tok[2])));
CREATE OR REPLACE MACRO is_person_name(core, given, surnames) AS
  coalesce(len(string_split(core, ' ')) BETWEEN 2 AND 4 AND regexp_full_match(core, '[A-Z]+( [A-Z]+)*')
           AND ssi_person_tokens(string_split(core, ' '), given, surnames), false);

-- Addresses ------------------------------------------------------------------------------------
-- USPS abbreviations and directionals (WEST left alone: often a street name). NORTHWEST is NW, one direction:
-- addr_split_dir read 805 SOUTHWEST BROADWAY as SOUTH + WEST, and keyed it 805 WEST (805 SW BROADWAY is 805 BROADWAY).
-- FREEWAY is FWY: DPR's Houston office is 3200 SW FREEWAY and 3200 SW FWY in OSHA's data
CREATE OR REPLACE MACRO clean_addr(s) AS trim(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(
 regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
   regexp_replace(regexp_replace(upper(coalesce(s, '')), '[^A-Z0-9 ]', ' ', 'g'), '\s+', ' ', 'g'),
   '\b(P O|POST OFFICE|P0)\s+BOX\b', 'PO BOX', 'g'),
   '\bSTREET\b', 'ST', 'g'), '\bAVENUE\b', 'AVE', 'g'), '\bROAD\b', 'RD', 'g'), '\bDRIVE\b', 'DR', 'g'),
   '\bBOULEVARD\b', 'BLVD', 'g'), '\bSUITE\b', 'STE', 'g'), '\bHIGHWAY\b', 'HWY', 'g'), '\bPARKWAY\b', 'PKWY', 'g'),
   '\b(FREEWAY|FRWY)\b', 'FWY', 'g'), '\b(EXPRESSWAY|EXPRESSWY|EXPWY)\b', 'EXPY', 'g'),
   '\bLANE\b', 'LN', 'g'), '\bCOURT\b', 'CT', 'g'), '\bPLACE\b', 'PL', 'g'), '\bCIRCLE\b', 'CIR', 'g'),
   '\bNORTHEAST\b', 'NE', 'g'), '\bNORTHWEST\b', 'NW', 'g'), '\bSOUTHEAST\b', 'SE', 'g'), '\bSOUTHWEST\b', 'SW', 'g'),
   '\bNORTH\b', 'N', 'g'), '\bSOUTH\b', 'S', 'g'), '\bEAST\b', 'E', 'g'),
 '\s+', ' ', 'g'));

-- Unit (suite, floor, #) kept separately so "1201 DEMONBREUN ST" and "... STE 200" are the same building
CREATE OR REPLACE MACRO addr_unit(s) AS
  nullif(regexp_extract(upper(coalesce(s, '')), '\b(STE|SUITE|UNIT|APT|FL|FLOOR|RM|ROOM|BLDG|#)\s*#?\s*([A-Z0-9-]+)\s*$', 0), '');

-- A direction written onto the street word after a house number is split off: OSHA writes one street both ways
-- (7900 WESTPARK DR / 7900 WEST PARK DR, Clark's McLean office; 3715 NORTHSIDE PKWY / 3715 N SIDE PKWY), which split
-- 21 companies' records in two. Not before ER (WESTERN, NORTHERN AVE) or fewer than 3 letters (WESTON, EASTON).
-- NORTHWESTERN HWY is split (31000 N WESTERN HWY is the same building); NORTHWEST is already NW (clean_addr).
-- Applied to a cleaned address (clean_addr), or to text holding one (a company profile's quote)
CREATE OR REPLACE MACRO addr_split_dir(s) AS
  regexp_replace(s, '\b([0-9]+[A-Z]? )(NORTH|SOUTH|EAST|WEST)([A-DF-Z][A-Z]{2,}|E[A-QS-Z][A-Z]+)\b', '\1\2 \3', 'g');

-- Address key: house number + first street word (skipping a leading directional), or "POBOX <n>".
-- Tolerates suffix variants ("7TH AVE SOUTH" = "7TH AVE S"), a direction written onto the street word, and suites.
CREATE OR REPLACE MACRO addr_key(s) AS CASE
  WHEN regexp_matches(clean_addr(s), '\bPO BOX\s+[0-9]+') THEN 'POBOX ' || regexp_extract(clean_addr(s), '\bPO BOX\s+([0-9]+)', 1)
  WHEN regexp_matches(clean_addr(s), '^[0-9]+[A-Z]?\s+') THEN
       regexp_extract(addr_split_dir(clean_addr(s)), '^([0-9]+)[A-Z]?\s+(?:(?:N|S|E|W|NORTH|SOUTH|EAST|WEST|NE|NW|SE|SW)\s+)?([A-Z0-9]+)', 1) || ' ' ||
       regexp_extract(addr_split_dir(clean_addr(s)), '^([0-9]+)[A-Z]?\s+(?:(?:N|S|E|W|NORTH|SOUTH|EAST|WEST|NE|NW|SE|SW)\s+)?([A-Z0-9]+)', 2)
  ELSE NULL END;

CREATE OR REPLACE MACRO zip5(z) AS CASE
  WHEN regexp_matches(trim(coalesce(z, '')), '^[0-9]{5}') AND substr(trim(z), 1, 5) <> '00000' THEN substr(trim(z), 1, 5)
  WHEN regexp_full_match(trim(coalesce(z, '')), '[0-9]{4}') THEN '0' || trim(z)
  ELSE NULL END;

-- Establishment key: stable across rebuilds (same cleaned inputs -> same key)
CREATE OR REPLACE MACRO establishment_key(clean, akey, z5, st) AS
  md5(coalesce(clean, '') || '|' || coalesce(akey, '') || '|' || coalesce(z5, '') || '|' || coalesce(st, ''));
