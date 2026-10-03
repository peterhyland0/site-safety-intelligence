-- Standard-code parsing: turns the raw `violation.standard` column into a code family, a
-- human-readable citation and a section key (the join key for ref_standard_hazard_map).
-- Persistent macros (no TEMP); safe to re-run (CREATE OR REPLACE). Pure SQL, DuckDB 1.4+.
--
-- Public macros
--   std_parse_with_state(raw, site_state) -> STRUCT(std_family, section_key, standard_cite)   <- use this in the pipeline
--   std_family_with_state(raw, site_state)    std_family(raw)
--   section_key_with_state(raw, site_state)   section_key(raw)
--   standard_cite_with_state(raw, site_state) standard_cite(raw)
--   std_natural_key(section_key)  -> zero-padded sort key used for `range` rows of the hazard map
-- The one-argument versions are the two-argument ones with site_state = NULL. The raw code alone is
-- ambiguous for some state-plan formats (bare Title 8 numbers, old packed digit strings), so the pipeline
-- should pass the citing inspection's site_state; without it those codes fall back to the most likely
-- family from the pattern (documented per rule below).
--
-- Families and their section-key / citation formats
--   federal_1926   '19260501 B13'          key '1926.501'          cite '1926.501(b)(13)'
--   federal_1910   '19101200 E01'          key '1910.1200'         cite '1910.1200(e)(1)'
--   federal_other  '19040039 A01'          key '1904.39'           cite '1904.39(a)(1)'     (1903 1904 1908 1915-1918 1928 1960)
--   general_duty   '5A0001'                key '5(a)(1)'           cite '5(a)(1)'           (OSH Act section 5(a); state clauses keep their state family)
--   state_WA       '296-155-24609(1)(A)'   key 'WAC 296-155-24609' cite 'WAC 296-155-24609(1)(a)'
--                  old packed (WA site):   '1550065701 A' = chapter 155, section 00657, para 01  -> 'WAC 296-155-657(1)(a)'
--   state_OR       'OAR 437-003-1501(1)'   key 'OAR 437-003-1501'  cite 'OAR 437-003-1501(1)'
--                  '40 CFR 170.311(B)(1)'  (EPA worker protection, enforced by Oregon OSHA) key '40 CFR 170.311'
--                  old packed (OR site, 1989-2014) '703150202' = OAR 437-003-1502(2); key 'OAR 437-003-1502'
--                  older packed divisions (1981-1993, e.g. '7831539') are undecoded: key 'OR-OLD 783'
--   state_MI       '408.40114(1)'          key 'R 408.40114'       cite 'R 408.40114(1)'    (administrative rules)
--                  '408.1011(A)'           key 'MCL 408.1011'      cite 'MCL 408.1011(a)'   (MIOSH Act sections, 4 digits)
--                  old packed '4084011401' = R 408.40114 para 01; '40801011' = MCL 408.1011
--                  'RULE 4(1)'             key 'MI RULE 4'         (MIOSHA COVID-19 emergency rules, 2020-21)
--   state_CA       '3395(H)' / '1509 B' / '15410001 A01'  key 'T8 CCR 3395' / 'T8 CCR 1509' / 'T8 CCR 1541.1'
--                  cite 'T8 CCR 3395(h)'; the packed 8-digit form is SSSS + 4-digit decimal (1541.1);
--                  '1430dddd'/'4300dddd' are recordkeeping section 14300.d; '6401dddd' is Labor Code 6401.d
--   state_other    any other state's own code: key '<ST> <code without paragraph>', cite '<ST> <raw>'
--   unknown        blank, no digits, or encoding damage
-- Paragraph letter case follows each code's convention where it can be inferred from depth:
--   CFR (a)(1)(i)(A) · WAC/MI (1)(a)(i)(A) · OAR (1)(a)(A)(i) · Title 8 (a)(1)(A)(i).

-- ---------------------------------------------------------------- helpers
CREATE OR REPLACE MACRO ssi_std_norm(raw) AS
  trim(regexp_replace(upper(coalesce(raw, '')), '\s+', ' ', 'g'));

CREATE OR REPLACE MACRO ssi_std_st(site_state) AS
  upper(trim(coalesce(site_state, '')));

-- 1..20 -> lowercase roman (old packed codes store roman paragraph levels as numbers)
CREATE OR REPLACE MACRO ssi_roman(n) AS
  CASE WHEN n BETWEEN 1 AND 20
       THEN ['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'][n]
       ELSE CAST(n AS VARCHAR) END;

-- digits -> integer text without leading zeros ('08' -> '8'); other text unchanged
CREATE OR REPLACE MACRO ssi_unpad(t) AS
  CASE WHEN regexp_full_match(t, '[0-9]{1,9}') THEN CAST(CAST(t AS BIGINT) AS VARCHAR) ELSE t END;

-- "(2)(E)(II)-1" -> "(2)(e)(ii)-1": parenthesised paragraph groups, lower-cased at the given depths
-- (1-based), numbers unpadded, anything after the last ')' kept. Tolerates a missing final ')'.
CREATE OR REPLACE MACRO ssi_paren_fmt(rest, lower_depths) AS
  CASE WHEN strpos(coalesce(rest, ''), '(') = 0 THEN coalesce(trim(rest), '')
  ELSE
    '(' || array_to_string(list_transform(regexp_extract_all(rest, '\(([^()]*)\)?', 1),
        lambda g, i: CASE WHEN regexp_full_match(trim(g), '[0-9]+') THEN ssi_unpad(trim(g))
                          WHEN list_contains(lower_depths, i) THEN lower(trim(g))
                          ELSE trim(g) END), ')(') || ')'
    || coalesce(regexp_extract(rest, '\)([^()]*)$', 1), '')
  END;

-- Natural sort key: every digit run left-padded to 12 so '1926.95' < '1926.501' < '1926.1053'.
CREATE OR REPLACE MACRO std_natural_key(k) AS
  CASE WHEN k IS NULL THEN NULL ELSE
    array_to_string(list_transform(regexp_extract_all(k, '[0-9]+|[^0-9]+'),
      lambda t: CASE WHEN regexp_full_match(t, '[0-9]+') THEN lpad(t, 12, '0') ELSE t END), '')
  END;

-- ---------------------------------------------------------------- federal (packed CFR)
-- 'PPPPSSSS' + paragraph tokens, e.g. '19260500 E01   IV', '19261408 B04 II A', '19260404 F07   IVC'.
-- Spaces are dropped and the tokens read as letter, number, roman, letter, number.
CREATE OR REPLACE MACRO ssi_fed_rest(s) AS regexp_replace(substr(s, 9), '[^A-Z0-9]', '', 'g');

CREATE OR REPLACE MACRO ssi_fed_para_m(m) AS
  CASE WHEN m.l1 <> '' THEN '(' || lower(m.l1) || ')' ELSE '' END
  || CASE WHEN m.l2 <> '' THEN '(' || ssi_unpad(m.l2) || ')' ELSE '' END
  || CASE WHEN m.l3 <> '' THEN '(' || lower(m.l3) || ')' ELSE '' END
  || CASE WHEN m.l4 <> '' THEN '(' || m.l4 || ')' ELSE '' END
  || CASE WHEN m.l5 <> '' THEN '(' || ssi_unpad(m.l5) || ')' ELSE '' END;

CREATE OR REPLACE MACRO ssi_fed_para(s) AS
  CASE
    WHEN ssi_fed_rest(s) = '' THEN ''
    WHEN regexp_full_match(ssi_fed_rest(s), '([A-Z]?)([0-9]{0,3})(X{0,3}(?:IX|IV|V?I{0,3}))([A-Z]?)([0-9]{0,2})')
      THEN ssi_fed_para_m(regexp_extract(ssi_fed_rest(s),
             '^([A-Z]?)([0-9]{0,3})(X{0,3}(?:IX|IV|V?I{0,3}))([A-Z]?)([0-9]{0,2})$', ['l1', 'l2', 'l3', 'l4', 'l5']))
    -- unparseable tail (e.g. old 1926.400(a) National Electrical Code references '19260400 A   011017'):
    -- first letter as the paragraph, the rest kept verbatim
    WHEN regexp_matches(ssi_fed_rest(s), '^[A-Z]')
      THEN '(' || lower(left(ssi_fed_rest(s), 1)) || ') ' || trim(substr(trim(substr(s, 9)), 2))
    ELSE ' ' || trim(substr(s, 9))
  END;

CREATE OR REPLACE MACRO ssi_fed_key(s) AS
  substr(s, 1, 4) || '.' || ssi_unpad(substr(s, 5, 4));

-- ---------------------------------------------------------------- Washington (WAC 296)
CREATE OR REPLACE MACRO ssi_wa_m(s) AS
  regexp_extract(s, '^296-([0-9]+)-([0-9]+)([A-Z]?)(.*)$', ['ch', 'sec', 'suf', 'rest']);
CREATE OR REPLACE MACRO ssi_wa_key(s) AS
  'WAC 296-' || ssi_wa_m(s).ch || '-' || ssi_wa_m(s).sec || lower(ssi_wa_m(s).suf);
CREATE OR REPLACE MACRO ssi_wa_cite(s) AS
  ssi_wa_key(s) || ssi_paren_fmt(ssi_wa_m(s).rest, [2, 3]);

-- old packed WA (1987-2015): CCC SSSSS [PP [PP]] [letter [nn [letter]]]; a 3-digit section is stored as 00SSS
CREATE OR REPLACE MACRO ssi_wa_old_m(s) AS
  regexp_extract(s, '^([0-9]{3})([0-9]{5})([0-9]{0,4}) ?(.*)$', ['ch', 'sec', 'p', 'tail']);
CREATE OR REPLACE MACRO ssi_wa_old_key(s) AS
  'WAC 296-' || ssi_unpad(ssi_wa_old_m(s).ch) || '-'
  || CASE WHEN starts_with(ssi_wa_old_m(s).sec, '00') THEN substr(ssi_wa_old_m(s).sec, 3) ELSE ssi_wa_old_m(s).sec END;
CREATE OR REPLACE MACRO ssi_old_tail_m(t) AS
  regexp_extract(regexp_replace(t, '[^A-Z0-9]', '', 'g'), '^([A-Z]?)([0-9]{0,2})([A-Z]?)([0-9]{0,2})$', ['a', 'n', 'b', 'm']);
CREATE OR REPLACE MACRO ssi_wa_old_cite(s) AS
  ssi_wa_old_key(s)
  || CASE WHEN length(ssi_wa_old_m(s).p) >= 2 THEN '(' || ssi_unpad(substr(ssi_wa_old_m(s).p, 1, 2)) || ')' ELSE '' END
  || CASE WHEN length(ssi_wa_old_m(s).p) = 4 THEN '(' || ssi_unpad(substr(ssi_wa_old_m(s).p, 3, 2)) || ')' ELSE '' END
  || CASE
       WHEN ssi_wa_old_m(s).tail = '' THEN ''
       WHEN regexp_full_match(regexp_replace(ssi_wa_old_m(s).tail, '[^A-Z0-9]', '', 'g'), '[A-Z]?[0-9]{0,2}[A-Z]?[0-9]{0,2}')
         THEN CASE WHEN ssi_old_tail_m(ssi_wa_old_m(s).tail).a <> '' THEN '(' || lower(ssi_old_tail_m(ssi_wa_old_m(s).tail).a) || ')' ELSE '' END
           || CASE WHEN ssi_old_tail_m(ssi_wa_old_m(s).tail).n <> '' AND CAST(ssi_old_tail_m(ssi_wa_old_m(s).tail).n AS INT) > 0
                   THEN '(' || ssi_roman(CAST(ssi_old_tail_m(ssi_wa_old_m(s).tail).n AS INT)) || ')' ELSE '' END
           || CASE WHEN ssi_old_tail_m(ssi_wa_old_m(s).tail).b <> '' THEN '(' || ssi_old_tail_m(ssi_wa_old_m(s).tail).b || ')' ELSE '' END
           || CASE WHEN ssi_old_tail_m(ssi_wa_old_m(s).tail).m <> '' THEN '(' || ssi_unpad(ssi_old_tail_m(ssi_wa_old_m(s).tail).m) || ')' ELSE '' END
       ELSE ' ' || ssi_wa_old_m(s).tail
     END;

-- ---------------------------------------------------------------- Oregon (OAR 437)
CREATE OR REPLACE MACRO ssi_or_m(s) AS
  regexp_extract(s, '^OAR 437-([0-9]{3})-([0-9]{4})([A-Z]?)(.*)$', ['div', 'sec', 'suf', 'rest']);
CREATE OR REPLACE MACRO ssi_or_key(s) AS
  'OAR 437-' || ssi_or_m(s).div || '-' || ssi_or_m(s).sec || ssi_or_m(s).suf;
CREATE OR REPLACE MACRO ssi_or_cite(s) AS
  ssi_or_key(s) || ssi_paren_fmt(ssi_or_m(s).rest, [2, 4]);
-- old packed Oregon (1989-2014, OR site): '70D' + 4-digit rule + paragraph digits = OAR 437-00D-SSSS,
-- e.g. '703150202' = OAR 437-003-1502(2), '701076506 A B' = OAR 437-001-0765(6)(a)(B)
CREATE OR REPLACE MACRO ssi_or_old_m(s) AS
  regexp_extract(s, '^70([0-7])([0-9]{4})([0-9]{0,2}) ?(.*)$', ['div', 'sec', 'p', 'tail']);
CREATE OR REPLACE MACRO ssi_or_old_key(s) AS
  CASE WHEN regexp_matches(s, '^70[0-7][0-9]{4}([0-9]{0,2})( |[A-Z]|$)')
       THEN 'OAR 437-00' || ssi_or_old_m(s).div || '-' || ssi_or_old_m(s).sec
       ELSE 'OR-OLD ' || left(s, 3) END;
CREATE OR REPLACE MACRO ssi_or_old_cite(s) AS
  CASE WHEN starts_with(ssi_or_old_key(s), 'OAR')
       THEN ssi_or_old_key(s)
            || CASE WHEN ssi_or_old_m(s).p <> '' THEN '(' || ssi_unpad(ssi_or_old_m(s).p) || ')' ELSE '' END
            || CASE WHEN ssi_or_old_m(s).tail = '' THEN ''
                    WHEN regexp_full_match(ssi_or_old_m(s).tail, '[A-Z]( +[A-Z])?')
                      THEN '(' || lower(left(ssi_or_old_m(s).tail, 1)) || ')'
                           || CASE WHEN length(ssi_or_old_m(s).tail) > 1 THEN '(' || right(ssi_or_old_m(s).tail, 1) || ')' ELSE '' END
                    ELSE ' ' || ssi_or_old_m(s).tail END
       ELSE 'OR ' || s END;

CREATE OR REPLACE MACRO ssi_cfr40_key(s) AS
  regexp_extract(s, '^(40 CFR [0-9]+\.[0-9]+)', 1);
CREATE OR REPLACE MACRO ssi_cfr40_cite(s) AS
  ssi_cfr40_key(s) || ssi_paren_fmt(substr(s, length(ssi_cfr40_key(s)) + 1), [1, 3]);

-- ---------------------------------------------------------------- Michigan (MIOSHA)
CREATE OR REPLACE MACRO ssi_mi_r_m(s) AS
  regexp_extract(s, '^(408|325)\.([0-9]{5})([A-Z]?)(.*)$', ['p', 'r', 'suf', 'rest']);
CREATE OR REPLACE MACRO ssi_mi_mcl_m(s) AS
  regexp_extract(s, '^(408|338)\.([0-9]{4})(.*)$', ['p', 'n', 'rest']);
CREATE OR REPLACE MACRO ssi_mi_rule_m(s) AS
  regexp_extract(s, '^RULE ?\(?([0-9]+)\)?(.*)$', ['n', 'rest']);
-- old packed: PPP RRRRR [PP [PP]] [letter][digit] [tail]; RRRRR starting with 0 is an MCL section (40801011 = MCL 408.1011)
CREATE OR REPLACE MACRO ssi_mi_old_m(s) AS
  regexp_extract(s, '^(408|325|309)([0-9]{5})([0-9]{0,4})([A-Z]?)([0-9]?) ?(.*)$', ['p', 'r', 'pp', 'a', 'd', 'tail']);
CREATE OR REPLACE MACRO ssi_mi_old_key(s) AS
  CASE WHEN starts_with(ssi_mi_old_m(s).r, '0')
       THEN 'MCL ' || ssi_mi_old_m(s).p || '.' || substr(ssi_mi_old_m(s).r, 2)
       ELSE 'R ' || ssi_mi_old_m(s).p || '.' || ssi_mi_old_m(s).r END;
CREATE OR REPLACE MACRO ssi_mi_old_cite(s) AS
  ssi_mi_old_key(s)
  || CASE WHEN length(ssi_mi_old_m(s).pp) >= 2 THEN '(' || ssi_unpad(substr(ssi_mi_old_m(s).pp, 1, 2)) || ')' ELSE '' END
  || CASE WHEN length(ssi_mi_old_m(s).pp) = 4 THEN '(' || ssi_unpad(substr(ssi_mi_old_m(s).pp, 3, 2)) || ')' ELSE '' END
  || CASE WHEN ssi_mi_old_m(s).a <> '' THEN '(' || lower(ssi_mi_old_m(s).a) || ')' ELSE '' END
  || CASE WHEN ssi_mi_old_m(s).d <> '' THEN '(' || ssi_mi_old_m(s).d || ')' ELSE '' END
  || CASE
       WHEN ssi_mi_old_m(s).tail = '' THEN ''
       WHEN regexp_full_match(ssi_mi_old_m(s).tail, '([A-Z])([0-9]{1,2})?')
         THEN '(' || lower(left(ssi_mi_old_m(s).tail, 1)) || ')'
              || CASE WHEN length(ssi_mi_old_m(s).tail) > 1 THEN '(' || ssi_unpad(substr(ssi_mi_old_m(s).tail, 2)) || ')' ELSE '' END
       ELSE ' ' || ssi_mi_old_m(s).tail
     END;

-- ---------------------------------------------------------------- California (Title 8 CCR)
-- current form '3395(H)', '341.1(H)(2)(B)', '5204(F)(2)(B)1.'
CREATE OR REPLACE MACRO ssi_ca_m(s) AS
  regexp_extract(s, '^([0-9]{3,5}(?:\.[0-9]+)?)([A-Z]?)(\(.*)?$', ['sec', 'suf', 'rest']);
-- older forms '1509 B', '1512 C01', '1640 B05 A', '342 A' and packed '15410001 A01' (SSSS + 4-digit decimal)
CREATE OR REPLACE MACRO ssi_ca_old_m(s) AS
  regexp_extract(s, '^([0-9]{3,8})(?: (.*))?$', ['num', 'tail']);
CREATE OR REPLACE MACRO ssi_ca_packed_sec(num) AS
  CASE
    WHEN length(num) = 7 THEN left(num, 3) || CASE WHEN right(num, 4) = '0000' THEN '' ELSE '.' || ssi_unpad(right(num, 4)) END  -- 3410001 = 341.1
    WHEN length(num) < 8 THEN num
    WHEN left(num, 4) IN ('1430', '4300') THEN '14300.' || ssi_unpad(substr(num, 5, 4))   -- recordkeeping 14300.x
    WHEN substr(num, 5, 4) = '0000' THEN left(num, 4)
    ELSE left(num, 4) || '.' || ssi_unpad(substr(num, 5, 4))
  END;
CREATE OR REPLACE MACRO ssi_ca_old_tail(t) AS
  CASE
    WHEN coalesce(t, '') = '' THEN ''
    WHEN regexp_full_match(t, '([A-Z])([0-9]{1,2})?(?: ([A-Z]+))?')
      THEN '(' || lower(left(t, 1)) || ')'
        || CASE WHEN regexp_extract(t, '^[A-Z]([0-9]{1,2})', 1) <> '' THEN '(' || ssi_unpad(regexp_extract(t, '^[A-Z]([0-9]{1,2})', 1)) || ')' ELSE '' END
        || CASE WHEN regexp_extract(t, ' ([A-Z]+)$', 1) <> '' THEN '(' || regexp_extract(t, ' ([A-Z]+)$', 1) || ')' ELSE '' END
    ELSE ' ' || t
  END;
CREATE OR REPLACE MACRO ssi_ca_key(s) AS
  CASE
    WHEN regexp_full_match(s, '[0-9]{3,5}(?:\.[0-9]+)?[A-Z]?(\(.*)?')
      THEN 'T8 CCR ' || ssi_ca_m(s).sec || lower(ssi_ca_m(s).suf)
    WHEN left(ssi_ca_old_m(s).num, 4) = '6401' AND length(ssi_ca_old_m(s).num) = 8
      THEN 'LC ' || ssi_ca_packed_sec(ssi_ca_old_m(s).num)
    ELSE 'T8 CCR ' || ssi_ca_packed_sec(ssi_ca_old_m(s).num)
  END;
CREATE OR REPLACE MACRO ssi_ca_cite(s) AS
  ssi_ca_key(s) ||
  CASE
    WHEN regexp_full_match(s, '[0-9]{3,5}(?:\.[0-9]+)?[A-Z]?(\(.*)?') THEN ssi_paren_fmt(ssi_ca_m(s).rest, [1, 4])
    ELSE ssi_ca_old_tail(ssi_ca_old_m(s).tail)
  END;

-- ---------------------------------------------------------------- other states (raw code, state-qualified)
CREATE OR REPLACE MACRO ssi_other_base(s) AS
  trim(CASE
    WHEN strpos(s, '(') > 1 THEN left(s, strpos(s, '(') - 1)
    -- packed number followed by space-separated paragraph tokens ('1904 32 A 1', '6 B', '17 IV B 1')
    WHEN regexp_matches(s, '^[0-9]+ ([A-Z]{1,4}|[A-Z]{1,2}[0-9]{1,3}|[0-9]{1,3})( |$)') THEN regexp_extract(s, '^([0-9]+) ', 1)
    ELSE s
  END);

-- ---------------------------------------------------------------- family
-- s: normalised code (ssi_std_norm), st: normalised site state ('' when unknown)
CREATE OR REPLACE MACRO ssi_std_family(s, st) AS
  CASE
    WHEN s LIKE 'GENERAL DUTY%' OR regexp_matches(s, '^5A000[0-9]') THEN 'general_duty'
    WHEN s = '' OR NOT regexp_matches(s, '[0-9]') OR strpos(s, '�') > 0 THEN 'unknown'
    WHEN regexp_matches(s, '^1926[0-9]{4}([^0-9]|$)') THEN 'federal_1926'
    WHEN regexp_matches(s, '^1910[0-9]{4}([^0-9]|$)') THEN 'federal_1910'
    WHEN regexp_matches(s, '^19(03|04|08|15|16|17|18|28|60)[0-9]{4}([^0-9]|$)') THEN 'federal_other'
    -- self-identifying state formats (pattern wins over site_state)
    WHEN regexp_matches(s, '^296-[0-9]+-[0-9]') THEN 'state_WA'
    WHEN regexp_matches(s, '^OAR 437-[0-9]{3}-[0-9]{4}') THEN 'state_OR'
    WHEN regexp_matches(s, '^(408|325)\.[0-9]{5}') AND st IN ('MI', '') THEN 'state_MI'
    WHEN regexp_matches(s, '^408\.[0-9]{4}([^0-9]|$)') AND st IN ('MI', '') THEN 'state_MI'
    -- formats that need the site state
    WHEN st = 'OR' AND (regexp_matches(s, '^40 CFR [0-9]+\.[0-9]+') OR regexp_matches(s, '^7[0-9]{6}')) THEN 'state_OR'
    WHEN st = 'WA' AND regexp_matches(s, '^[0-9]{8}') THEN 'state_WA'
    WHEN st = 'MI' AND (regexp_matches(s, '^(408|325|309)[0-9]{5}') OR regexp_matches(s, '^338\.[0-9]{4}')
                        OR regexp_matches(s, '^RULE ?\(?[0-9]')) THEN 'state_MI'
    WHEN st = 'CA' AND (regexp_full_match(s, '[0-9]{3,5}(?:\.[0-9]+)?[A-Z]?(\(.*)?')
                        OR regexp_full_match(s, '[0-9]{3,8}( .*)?')) THEN 'state_CA'
    WHEN st <> '' THEN 'state_other'
    -- no site_state: best guess from the pattern (each guess is >= 95% one state in the 1972-2026 data)
    WHEN regexp_matches(s, '^(408|325)[0-9]{5}') THEN 'state_MI'
    WHEN regexp_matches(s, '^155[0-9]{5}') THEN 'state_WA'
    WHEN regexp_full_match(s, '[0-9]{4}(?:\.[0-9]+)?(\(.*)?') THEN 'state_CA'
    ELSE 'state_other'
  END;

CREATE OR REPLACE MACRO ssi_std_key(s, st, fam) AS
  CASE fam
    WHEN 'unknown' THEN NULL
    WHEN 'general_duty' THEN
      CASE WHEN regexp_matches(s, '^5A000[0-9]') THEN '5(a)(' || substr(s, 6, 1) || ')' ELSE '5(a)(1)' END
    WHEN 'federal_1926' THEN ssi_fed_key(s)
    WHEN 'federal_1910' THEN ssi_fed_key(s)
    WHEN 'federal_other' THEN ssi_fed_key(s)
    WHEN 'state_WA' THEN CASE WHEN starts_with(s, '296-') THEN ssi_wa_key(s) ELSE ssi_wa_old_key(s) END
    WHEN 'state_OR' THEN
      CASE WHEN starts_with(s, 'OAR ') THEN ssi_or_key(s)
           WHEN starts_with(s, '40 CFR') THEN ssi_cfr40_key(s)
           ELSE ssi_or_old_key(s) END
    WHEN 'state_MI' THEN
      CASE WHEN regexp_matches(s, '^(408|325)\.[0-9]{5}') THEN 'R ' || ssi_mi_r_m(s).p || '.' || ssi_mi_r_m(s).r || lower(ssi_mi_r_m(s).suf)
           WHEN regexp_matches(s, '^(408|338)\.[0-9]{4}') THEN 'MCL ' || ssi_mi_mcl_m(s).p || '.' || ssi_mi_mcl_m(s).n
           WHEN starts_with(s, 'RULE') THEN 'MI RULE ' || ssi_mi_rule_m(s).n
           ELSE ssi_mi_old_key(s) END
    WHEN 'state_CA' THEN ssi_ca_key(s)
    ELSE CASE WHEN st <> '' THEN st || ' ' ELSE '' END || ssi_other_base(s)
  END;

CREATE OR REPLACE MACRO ssi_std_cite(s, st, fam) AS
  CASE fam
    WHEN 'unknown' THEN nullif(s, '')
    WHEN 'general_duty' THEN ssi_std_key(s, st, fam)
    WHEN 'federal_1926' THEN ssi_fed_key(s) || ssi_fed_para(s)
    WHEN 'federal_1910' THEN ssi_fed_key(s) || ssi_fed_para(s)
    WHEN 'federal_other' THEN ssi_fed_key(s) || ssi_fed_para(s)
    WHEN 'state_WA' THEN CASE WHEN starts_with(s, '296-') THEN ssi_wa_cite(s) ELSE ssi_wa_old_cite(s) END
    WHEN 'state_OR' THEN
      CASE WHEN starts_with(s, 'OAR ') THEN ssi_or_cite(s)
           WHEN starts_with(s, '40 CFR') THEN ssi_cfr40_cite(s)
           ELSE ssi_or_old_cite(s) END
    WHEN 'state_MI' THEN
      CASE WHEN regexp_matches(s, '^(408|325)\.[0-9]{5}')
             THEN 'R ' || ssi_mi_r_m(s).p || '.' || ssi_mi_r_m(s).r || lower(ssi_mi_r_m(s).suf) || ssi_paren_fmt(ssi_mi_r_m(s).rest, [2, 3])
           WHEN regexp_matches(s, '^(408|338)\.[0-9]{4}')
             THEN 'MCL ' || ssi_mi_mcl_m(s).p || '.' || ssi_mi_mcl_m(s).n || ssi_paren_fmt(ssi_mi_mcl_m(s).rest, [1, 3])
           WHEN starts_with(s, 'RULE') THEN 'MI Rule ' || ssi_mi_rule_m(s).n || ssi_paren_fmt(ssi_mi_rule_m(s).rest, [2, 3])
           ELSE ssi_mi_old_cite(s) END
    WHEN 'state_CA' THEN ssi_ca_cite(s)
    ELSE CASE WHEN st <> '' THEN st || ' ' ELSE '' END || s
  END;

-- ---------------------------------------------------------------- public API
CREATE OR REPLACE MACRO std_family_with_state(raw, site_state) AS
  ssi_std_family(ssi_std_norm(raw), ssi_std_st(site_state));

CREATE OR REPLACE MACRO section_key_with_state(raw, site_state) AS
  ssi_std_key(ssi_std_norm(raw), ssi_std_st(site_state), std_family_with_state(raw, site_state));

CREATE OR REPLACE MACRO standard_cite_with_state(raw, site_state) AS
  ssi_std_cite(ssi_std_norm(raw), ssi_std_st(site_state), std_family_with_state(raw, site_state));

CREATE OR REPLACE MACRO std_parse_with_state(raw, site_state) AS
  struct_pack(
    std_family    := std_family_with_state(raw, site_state),
    section_key   := section_key_with_state(raw, site_state),
    standard_cite := standard_cite_with_state(raw, site_state));

CREATE OR REPLACE MACRO std_family(raw) AS std_family_with_state(raw, NULL);
CREATE OR REPLACE MACRO section_key(raw) AS section_key_with_state(raw, NULL);
CREATE OR REPLACE MACRO standard_cite(raw) AS standard_cite_with_state(raw, NULL);
