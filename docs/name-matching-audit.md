# Name-matching audit: company and person names

What was checked, what was wrong, and the test that now holds each answer in place. Every figure below is from the
10-year warehouse (237,113 distinct raw employer names, 121,108 name cores), measured before and after the fixes.

## How it was checked

- **The cleaning macros** ([ssi/cleaning/macros.sql](../ssi/cleaning/macros.sql)) were run on crafted edge cases,
  then on every raw name in the warehouse. Each kind of mangled name was counted, along with how many have a twin
  (the same company's name cleaned differently).
- **People's names**: the Python rule ([candidates.is_person_core](../ssi/matching/candidates.py)) was compared with
  the build's `core_stats.is_person` on all 121,108 cores (0 disagreements before and after). Then:
  - *Misses*: cores rated "distinctive" that look like a person (a common surname plus name-like words), in 2+ states.
  - *False hits*: cores rated "person" that start with a place word.
- **The rules** ([rules.py](../ssi/matching/rules.py)): Jaro-Winkler and `typo_equal` were tried on pairs of
  different family names. Then every pair of differently named establishments in one non-shared building was
  collected (the population M2's fuzzy branch can merge) and sorted into typos, extensions, trade swaps, JVs and
  different people.
- **End to end**: a mini warehouse built from hand-written OSHA records by the real pipeline SQL. `run.match` runs on
  it exactly as for a GC (search, spelling correction, tiers, address expansion, rules).
- **The matching eval** (silver labels from ITA tax IDs) was run before and after, on warehouses built from the same
  raw files.

## Findings and fixes

### Cleaning (each fix changes establishment keys: rebuild with `make build`)

643 raw names now clean differently; 116 of their old cleaned names merge into another company's existing one (its
twin). One name splits: `J B T C VENTURES` now joins as `JBTC`, as `J.B.T.C.` always did, apart from a record
typed `JB TC VENTURES` (the pairwise joining had made both `JB TC`).

| Found | In the data | Effect | Fix |
|---|---|---|---|
| Legal forms not stripped: `L.C.`, `LIMITED LIABILITY COMPANY`, `LLLP`, `PLC`, the `LCC` slip, `CO.INC`, cut-off `INCORPORA…`/`CORPORATIO…` | 247 raw names; **58 merge with a twin** | Split companies. `ADELPHI CONSTRUCTION LC` has core `ADELPHI LC`, so **X1 excluded it** for a GC entering "Adelphi Construction" | Added to n9 (PA left alone: `ARSENAL SCAFFOLD OF PA`) |
| `A-1 ROOFING` → `A 1 ROOFING`, not `A1 ROOFING` | 279 raw names; 31 twins | The GC's "A-1 Roofing" never found `A1 ROOFING` (no searchable word) | n10 joins a single letter and a 1-3 digit number |
| Runs of 4+ initials joined in pairs: `H V A C` → `HV AC`, `V I S E` → `VI SE` | 63 raw names; 15 twins | Split from the dotted spelling | n10 joins any run in one pass |
| `R G P INC` → **`R`**; `J L P CONSTRUCTION` → core `J` | none mangled in the data; any GC entry | `L P`/`G P` became a legal form before the initials joined, then n9 stripped it: one company's name becomes every `R, INC.` | n8 joins `L P`/`G P` only after a word |
| `ABC CONSTRUCTION (JV)` → `ABC CONSTRUCTION`, `is_jv` false | 0 in the data; any GC entry | A joint venture merged into its member (the README says JVs never are) | n5 keeps `(JV)` |
| `AKA ELECTRIC` → `DBA ELECTRIC` (core empty) | 13 raw names | A real company's name turned into a generic one | n4 converts AKA/DBA only after a name |
| `CRAIG HANES, INC, DBA` and `ANDREWS GROUP THE LLC` | 45 raw names; 13 twins | Split | n9 strips a dangling DBA and a THE before a legal form |
| `O´BRIEN`, `O‘BRIEN`, `OʼBRIEN` → `O BRIEN` | 0 in OSHA's data (it is ASCII); GC entries | Split from `OBRIEN` | n3 deletes every apostrophe |
| PDF ligatures and full-width letters deleted (`ﬂoor` → `OOR`, `ＢＲＡＳＦＩＥＬＤ` → empty) | GC entries pasted from documents | A sub with no name at all | n1 folds them (DuckDB has no NFKC) |
| `START2FINISHNJ - ROOFING` → `ROOFING` | 0 in the data | A company's name eaten as an Arizona case number | n2 needs 4+ digits, the build check's own test |

**Macro size.** A macro's argument is pasted in wherever it is used. Fixes written with `CASE WHEN … s … THEN s ELSE
… s …` therefore multiplied the expression: the n1 step appeared 36 times inside `clean_name`. The lookup of a sub's
own name (`describe_query`, which calls `clean_name` 7 times) went from 306 ms to 1.9 s. Steps that need their
input twice now take it through a lambda. `describe_query` cleans once in a subquery: **10 ms**. A rebuild with the
lambda form gives table checksums identical to the CASE form.

### People's names

| Found | In the data | Effect | Fix |
|---|---|---|---|
| Common given names missing: ALEX, EDGAR, JOEL, JOSUE, IVAN, RENE, CHRISTIAN, ELMER, … (113 added, picked from the first words of person-like cores in the data) | ALEX PEREZ: 7 establishments in 5 states, "distinctive" | **M3 auto-matched one person's records across states**, the error the person tier exists to stop | ref/given_name.csv |
| Initial + surname (`J LOPEZ`, `R GARCIA`) never a person | J LOPEZ: 8 establishments in 7 states | Same | Rule: 2 words, a single letter then a common surname (new ref/surname.csv, everyday words like STONE, DAY, PARK left out) |
| Surname, given name, middle initial (`MORALES JAVIER M`) | 31 cores | Same | Rule: 3 words, the 2nd a given name, the 3rd an initial |
| Place names rated as people: SAN JOAQUIN, SAN ANTONIO, ST GEORGE, SANTA MARIA, … | 27 cores | A company's own branch in another city excluded (X5) | 2-word surname-first rule skips SAN, SANTA, ST, FORT, MT, PORT, LOS, LAS, LAKE, CAPE (not LA/EL/DEL: `L A HOWARD` cleans to `LA HOWARD`) |

Net: 3,410 more cores rated "person" (20,988 → 24,398), 27 fewer. The candidates were reviewed by hand. Names that
also start well-known companies were left out: ALLAN (Allan Myers), BEN (Ben Hur), MARTIN (Martin Marietta),
ORLANDO, MILTON, GERMAN, JAY. The rule now lives in one macro, `is_person_name`, used by both pipeline steps that
had their own copy (core_stats and the related-facility scope). Python mirrors it, and a test compares the two on
~40,000 generated cores and all real ones.

### Rules

| Found | In the data | Effect | Fix |
|---|---|---|---|
| M2's fuzzy branch (Jaro-Winkler ≥ 0.93 of the full names, at a matched address) merges any similar name. The branch meant for typos (`typo_equal`) can never fire: it also requires the names to differ only by generic words | 1,990 differently named pairs share a non-shared building | Mostly real typos. But also **7 JVs into their members**, **9 trade-word sister companies** (`EENIGENBURG FRAMING`/`ROOFING`; U3 already calls these sisters, but only when the names are short enough to score under 0.93) and **10 different people** (`MARIO`/`MAURICIO CONTRERAS`, `SERGIO CAZARES`/`… SR`) | J1 (JV vs non-JV), U3 (a trade word swapped, not added: `SMITH ROOFING SIDING` still matches) and P2 (no given name in common, or another generation). All "uncertain", so the AI or the GC decides |
| The address pass let a decision replace an earlier one only if it was MATCHED | Every guard above, R1 aside | The same record was "uncertain" or "excluded" depending on whether the name search had found it first | An address-aware "uncertain" now replaces a name-only "excluded" |
| Spelling correction tried OSHA's dominant spelling before the GC's city | `BRINKMMAN CONSTRUCTION, Wheat Ridge` (a slip of BRINKMAN, which has a record there) | Searched BRINKMANN (25 inspections, a St. Louis builder) and auto-matched its records | The city test first, then volume |
| `correct_spelling` replaced the core as a substring (`SERVICES ICE` with ICE → ACE gave `SERVACES ICE`), or the whole name when the core's words weren't together, and dropped the sub's other names (DBA, legal name, licence names) | `ALPHA ROOFING EXPERTS` (licence, Monitor WA) was searched as `ALPHA EXPERT`, losing ROOFING; any corrected entry with a DBA | The record under the DBA was judged against the corrected legal name and excluded; ALPHA ROOFING EXPERT in Monitor became a "different trade" question | `respell` swaps whole words; aliases kept, and respelt |

## Effect

| | Before | After |
|---|---|---|
| Establishments | 218,004 | 217,931 |
| Distinct cleaned names | 175,438 | 175,308 |
| Distinct names, all years (build report) | 800,745 | 798,166 |
| Cores rated person / distinctive | 20,988 / 91,036 | 24,398 / 87,483 |
| Related-facility inspections | 10,713 | 10,689 |
| Build checks | all pass | all pass |
| `describe_query` (each sub's name) | 306 ms | 10 ms |

Matching eval (300 silver pairs; the sample is drawn by establishment key, and 73 keys changed):

| | Before | After |
|---|---|---|
| Precision of automatic matches | 0.845 | 0.845 |
| Recall of automatic matches | 0.653 | 0.653 |
| Candidate recall | 0.947 | 0.947 |
| Same-company records wrongly excluded | 0.013 | 0.013 |
| Different companies kept out | 0.88 | 0.88 |
| A GC's slip: same matches as the correct spelling | 325 of 381 | **356 of 383** |
| … a match the correct spelling doesn't make | 0 | 0 (BRINKMMAN was 1 before the city-first fix) |
| Licensed contractors one letter off, same address, auto-matched | 19 of 72 | 22 of 66 |
| … another address, auto-matched | 4 of 130 | 5 of 119 (ALPHA ROOFING EXPERT(S), Monitor WA: a PO box, same company) |
| Eval run time | 469 s | 114 s |

The pair outcomes are unchanged: the fixes act on the cases above, which the 300 silver pairs rarely contain (one
pair moved from "same core" to "same name" because its two names now clean alike). The sample sizes for slips and
licences moved because those samples are drawn from the rebuilt tables.

## What is left (known, not fixed)

- **`typo_equal` treats different family names as slips** (HERNANDEZ/FERNANDEZ 0.97, JOHNSON/JOHNSTON,
  MEJIA/MEDINA). It never matches anything on its own: X1 skips it, S1 makes it uncertain, and spelling correction
  needs a distinctive, ≥10× dominant spelling. Tests pin that down for people's names and real words.
- **Companies named after a person** (DAN RYAN, JOHN MORIARTY, MARC JONES) are rated "person". Their records in
  another city used to be excluded (X5); since the per-rule eval (eval/rules) measured that, rule P3 asks about them
  instead when both names carry a trade or company word (JOHN MORIARTY ASSOCIATES) or both carry a legal form. A
  company named after a person but written bare on one side (typed "Dan Ryan", or a record with no legal form) is
  still excluded in another city. ALLAN and BEN were held back from the given names for this reason. A first name that
  is also a surname or company word (MARTIN GARCIA: 5 states) is still rated by rarity.
- **Nicknames are different people to P2** (DAVE/DAVID ALLEN at one address): the record goes to review, not matched.
- **Addresses**: `3021 SEVENTH AVENUE` and `3021 7TH AVE` are different address keys, so M2 can't see they're one
  building.
- `C/O …` and `FORMERLY …` stay in the name (5 and 6 names). `… P C` at the end becomes `PC` after n9 has run, so
  cleaning it twice strips it (the one case where `clean_name` isn't idempotent: "PURCELL P & C" is a name).
- The 3-4 digit ID rule (`1234 - `) catches one name in the data, an address-named LLC (`1121 - 1125 CLEMENT STREET`).
- The project duplicate check treats two people with the same name in one state as one sub.
- A GC's slip in a name's first letter is never searched (candidate search blocks on the first letter).
- Vietnamese and other surname-first names of 3+ words (`NGUYEN VAN TUAN`) are not recognised as people.

## The tests

| File | What it holds | Needs |
|---|---|---|
| [tests/test_cleaning.py](../tests/test_cleaning.py) | Every finding above as a SAME / DIFFERENT / EXACT case. Properties over many spellings of each name: legal forms, ID prefixes, THE, case, accents, spacing and initials never split a company. Output alphabet on fuzz input; steps compose to `clean_name`; cleaning twice changes nothing | nothing |
| [tests/test_person_names.py](../tests/test_person_names.py) | Who is and isn't a person (incl. places and well-known firms); Python = SQL on ~40k cores; the GC's entry is cleaned before it is rated; hygiene of the name lists | nothing |
| [tests/test_matching_rules.py](../tests/test_matching_rules.py) | J1, U3 and P2 at the address; `trade_swap`, `different_people`, `respell`, aliases kept. Properties: a person's name is never matched outside the GC's city, nor another person's name or another real word without an address | nothing |
| [tests/test_name_matching_e2e.py](../tests/test_name_matching_e2e.py) | 19 GC entries through `run.match` on a mini warehouse built by the pipeline's SQL ([tests/mini_warehouse.py](../tests/mini_warehouse.py)): Brasfield, Adelphi, A-1, RGP, JVs, sister companies, the DBA, the red-flag net, a registered agent, ALEX PEREZ, J LOPEZ, JOSE HERNANDEZ, MARIO/MAURICIO, SAN ANTONIO | nothing |
| [tests/test_warehouse_names.py](../tests/test_warehouse_names.py) | On every establishment and core: alphabet, no legal form or dangling DBA left, no paired initials, every JV flagged, Python = build on all cores, no person rated distinctive, place names not people | a warehouse built from the current rules (else skipped, saying so) |

On the code before the fixes, 12 of the 19 end-to-end scenarios fail, and so do 59 cleaning cases and 18 rule tests
(the person-name tests don't import: the rule's new parts don't exist there).
