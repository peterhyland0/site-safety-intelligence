# Matching evaluation (silver labels from ITA EINs)

300 pairs (150 positive, 150 negative), 146 s.

| Metric | Value |
|---|---|
| matched_precision | 0.901 |
| matched_recall | 0.607 |
| candidate_recall | 0.953 |
| positives_left_uncertain | 0.333 |
| false_exclusion_rate | 0.013 |
| negatives_kept_out | 0.933 |

## Outcome by pair type

| Pair type | matched | uncertain | excluded | not found |
|---|---|---|---|---|
| different_name | 0 | 2 | 2 | 6 |
| same_core_different_ein | 6 | 26 | 103 | 1 |
| same_name_different_ein | 4 | 10 | 0 | 0 |
| same_name_other_address | 91 | 48 | 0 | 1 |

## Disagreements with the silver label (first 20)

| Label | Query (A) | Candidate (B) | Outcome | Rule |
|---|---|---|---|---|
| same | CB I STORAGE TANK SOLUTIONS (PLAINFIELD, IL) | CB I (PLAINFIELD, IL) | excluded | X1 |
| same | PCL CONSTRUCTION SERVICES (GLENDALE, CA) | PCL CONSTRUCTION (DENVER, CO) | excluded | X3 |
| different | JF SHEA CONSTRUCTION (WALNUT, CA) | JF SHEA (WALNUT, CA) | matched | M1b |
| different | MCCROSSIN FOUNDATIONS (BELLEFONTE, PA) | MCCROSSIN FOUNDATIONS (SEWICKLEY, PA) | matched | M1 |
| different | PARKING STRUCTURES (THOMPSON, OH) | PARKING STRUCTURES SERVICES (THOMPSON, OH) | matched | M1b |
| different | HOUCK SERVICES (HARRISBURG, PA) | HOUCK (HARRISBURG, PA) | matched | M1b |
| different | HENKEL CONSTRUCTION (MASON CITY, IA) | HENKEL GENERAL CONSTRUCTION (MASON CITY, IA) | matched | M1b |
| different | RD GRAHAM ELECTRIC (HIGH POINT, NC) | RD GRAHAM ELECTRIC (GREENSBORO, NC) | matched | M1 |
| different | JAKE MARSHALL SERVICE (CHATTANOOGA, TN) | JAKE MARSHALL (CHATTANOOGA, TN) | matched | M1b |
| different | HOUCK SERVICES (HARRISBURG, PA) | HOUCK (HARRISBURG, PA) | matched | M1b |
| different | BOPAT ELECTRIC (FREDERICK, MD) | BOPAT ELECTRIC (COLUMBIA, MD) | matched | M1 |
| different | BL SHEET METAL ROOFING (BLOOMINGTON, IN) | BL SHEET METAL ROOFING (BLOOMINGTON, IN) | matched | M1 |
