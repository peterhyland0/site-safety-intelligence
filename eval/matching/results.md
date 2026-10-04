# Matching evaluation (silver labels from ITA EINs)

300 pairs (150 positive, 150 negative), 114 s.

| Metric | Value |
|---|---|
| matched_precision | 0.845 |
| matched_recall | 0.653 |
| candidate_recall | 0.947 |
| positives_left_uncertain | 0.28 |
| false_exclusion_rate | 0.013 |
| negatives_kept_out | 0.88 |

## Outcome by pair type

| Pair type | matched | uncertain | excluded | not found |
|---|---|---|---|---|
| different_name | 0 | 5 | 2 | 8 |
| same_core_different_ein | 12 | 42 | 89 | 0 |
| same_name_different_ein | 6 | 1 | 0 | 0 |
| same_name_other_address | 98 | 37 | 0 | 0 |

## Disagreements with the silver label (first 20)

| Label | Query (A) | Candidate (B) | Outcome | Rule |
|---|---|---|---|---|
| same | DR HORTON INC GREENSBORO (HIGH POINT, NC) | DR HORTON (KINGSPORT, TN) | excluded | X1 |
| same | DR HORTON INC GREENSBORO (HIGH POINT, NC) | DR HORTON (HIGH POINT, NC) | excluded | X1 |
| different | CRITCHFIELD MECHANICAL (SAN JOSE, CA) | CRITCHFIELD MECHANICAL (HUNTINGTON BEACH, CA) | matched | M1 |
| different | JAKE MARSHALL (CHATTANOOGA, TN) | JAKE MARSHALL SERVICE (CHATTANOOGA, TN) | matched | M1b |
| different | NOR SON CONSTRUCTION (BAXTER, MN) | NOR SON (BAXTER, MN) | matched | M2 |
| different | BAKER CONCRETE CONSTRUCTION (MONROE, OH) | BAKER CONCRETE CONSTRUCTORS (MONROE, OH) | matched | M2 |
| different | DR HORTON (HIGH POINT, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | CONCRETE PLACEMENT (SANTA ANA, CA) | AMERICAN CONCRETE PLACEMENT (ANDERSON, CA) | matched | M1b |
| different | DR HORTON (MORRISVILLE, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | HAGERMAN CONSTRUCTION (FORT WAYNE, IN) | HAGERMAN (FISHERS, IN) | matched | M1b |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M1b |
| different | CHRISTMAN CONSTRUCTORS (LANSING, MI) | CHRISTMAN (LANSING, MI) | matched | M1b |
| different | HAGERMAN CONSTRUCTION (FISHERS, IN) | HAGERMAN (FISHERS, IN) | matched | M1b |
| different | BOPAT ELECTRIC (FREDERICK, MD) | BOPAT ELECTRIC (COLUMBIA, MD) | matched | M1 |
| different | DORAN COMPANIES (MINNEAPOLIS, MN) | DORAN CONSTRUCTION (MINNEAPOLIS, MN) | matched | M2 |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M1b |
| different | MCCLURE SONS (MILL CREEK, WA) | MCCLURE BROTHERS (MILL CREEK, WA) | matched | M2 |
| different | DR HORTON (MORRISVILLE, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | HENKEL CONSTRUCTION (MASON CITY, IA) | HENKEL GENERAL CONSTRUCTION (MASON CITY, IA) | matched | M1b |
| different | DR HORTON (CHARLOTTE, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |

## Typos

383 slips in distinctive OSHA names, searched with the name's city and state.

| Outcome | Count |
|---|---|
| same matches as the correct spelling | 356 |
| fewer (the rest left for the AI reviewer and the GC) | 27 |
| a match the correct spelling doesn't make | 0 |

Licensed contractors with no OSHA record, one letter from an OSHA name in the same city:

| Case | Matched automatically |
|---|---|
| same address (a slip) | 22 of 66 |
| another address (usually another company) | 5 of 119 |
- ALPHA ROOFING EXPERTS LLC (Monitor, WA) matched ALPHA EXPERT
- COLUMBIA CROSSING CONSTRUCTION LLC (Portland, OR) matched COLUMBIA CROSSINGS
- HUIZENGA BROS CONST INC (Deming, WA) matched HUIZENGA CONSTR
- PLUMBING TECH REPIPE SPECIALISTS INC (San Jose, CA) matched REPIPE SPECIALIST
- SANDESSEE ELECTRIC (Pasco, WA) matched SANDESSE
