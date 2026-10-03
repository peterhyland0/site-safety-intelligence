# Matching evaluation (silver labels from ITA EINs)

300 pairs (150 positive, 150 negative), 97 s.

| Metric | Value |
|---|---|
| matched_precision | 0.846 |
| matched_recall | 0.66 |
| candidate_recall | 0.94 |
| positives_left_uncertain | 0.267 |
| false_exclusion_rate | 0.013 |
| negatives_kept_out | 0.88 |

## Outcome by pair type

| Pair type | matched | uncertain | excluded | not found |
|---|---|---|---|---|
| different_name | 1 | 4 | 2 | 9 |
| same_core_different_ein | 12 | 40 | 92 | 0 |
| same_name_different_ein | 6 | 0 | 0 | 0 |
| same_name_other_address | 98 | 36 | 0 | 0 |

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

LangSmith experiment: `rules-75bea227`
