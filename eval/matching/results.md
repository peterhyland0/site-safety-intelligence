# Matching evaluation (silver labels from ITA EINs)

300 pairs (150 positive, 150 negative), 96 s.

| Metric | Value |
|---|---|
| matched_precision | 0.831 |
| matched_recall | 0.687 |
| candidate_recall | 0.96 |
| positives_left_uncertain | 0.273 |
| false_exclusion_rate | 0.0 |
| negatives_kept_out | 0.86 |

## Outcome by pair type

| Pair type | matched | uncertain | excluded | not found |
|---|---|---|---|---|
| different_name | 0 | 1 | 0 | 6 |
| same_core_different_ein | 11 | 26 | 101 | 0 |
| same_name_different_ein | 10 | 2 | 0 | 0 |
| same_name_other_address | 103 | 40 | 0 | 0 |

## Disagreements with the silver label (first 20)

| Label | Query (A) | Candidate (B) | Outcome | Rule |
|---|---|---|---|---|
| different | DR HORTON (MORRISVILLE, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | PIPE JACKING TRENCHLESS (VISTA, CA) | PIPE JACKING TRENCHLESS (SAN DIEGO, CA) | matched | M1 |
| different | HAGERMAN (FORT WAYNE, IN) | HAGERMAN CONSTRUCTION (FISHERS, IN) | matched | M1b |
| different | JAKE MARSHALL (CHATTANOOGA, TN) | JAKE MARSHALL SERVICE (CHATTANOOGA, TN) | matched | M1b |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M1b |
| different | NOR SON CONSTRUCTION (BAXTER, MN) | NOR SON (BAXTER, MN) | matched | M2 |
| different | HENSEL PHELPS (HONOLULU, HI) | HENSEL PHELPS CONSTRUCTION (KANEOHE, HI) | matched | M1b |
| different | DR HORTON (HIGH POINT, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | STELLAR CONTRACTING (JACKSONVILLE, FL) | STELLAR GROUP (JACKSONVILLE, FL) | matched | M2 |
| different | HAGERMAN CONSTRUCTION (FORT WAYNE, IN) | HAGERMAN (FISHERS, IN) | matched | M1b |
| different | DR HORTON (ARLINGTON, TX) | DR HORTON (SAN ANTONIO, TX) | matched | M1 |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M1b |
| different | DR HORTON (HIGH POINT, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | DR HORTON (PLEASANTON, CA) | DR HORTON (ROSEVILLE, CA) | matched | M1 |
| different | PERFORMANCE CONSTRUCTION (POTTSVILLE, PA) | PERFORMANCE CONSTRUCTION SERVICES (POTTSVILLE, PA) | matched | M2 |
| different | BRANAGH HOLDINGS (LAFAYETTE, CA) | BRANAGH (OAKLAND, CA) | matched | M1b |
| different | DR HORTON (BILTMORE FOREST, NC) | DR HORTON (RALEIGH, NC) | matched | M1 |
| different | DR HORTON (OKLAHOMA CITY, OK) | DR HORTON (TULSA, OK) | matched | M1 |
| different | DR HORTON (FORT WORTH, TX) | DR HORTON (SAN ANTONIO, TX) | matched | M1 |
| different | TRINE CONSTRUCTION (WEST CHICAGO, IL) | TRINE CONSTRUCTION (SAINT CHARLES, IL) | matched | M1 |
