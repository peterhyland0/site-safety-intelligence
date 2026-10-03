# Matching evaluation (silver labels from ITA EINs)

300 pairs (150 positive, 150 negative), 141 s.

| Metric | Value |
|---|---|
| matched_precision | 0.881 |
| matched_recall | 0.64 |
| candidate_recall | 0.96 |
| positives_left_uncertain | 0.307 |
| false_exclusion_rate | 0.013 |
| negatives_kept_out | 0.913 |

## Outcome by pair type

| Pair type | matched | uncertain | excluded | not found |
|---|---|---|---|---|
| different_name | 1 | 1 | 2 | 6 |
| same_core_different_ein | 8 | 29 | 103 | 2 |
| same_name_different_ein | 5 | 3 | 0 | 0 |
| same_name_other_address | 95 | 45 | 0 | 0 |

## Disagreements with the silver label (first 20)

| Label | Query (A) | Candidate (B) | Outcome | Rule |
|---|---|---|---|---|
| same | TRANE US (GREENVILLE, SC) | TRANE (BROKEN ARROW, OK) | excluded | X1 |
| same | MICHELS COMMUNICATIONS (BROWNSVILLE, WI) | MICHELS (MILWAUKEE, WI) | excluded | X1 |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M2 |
| different | LOBAR (DILLSBURG, PA) | LOBAR ASSOCIATES (DILLSBURG, PA) | matched | M2 |
| different | BRANAGH HOLDINGS (LAFAYETTE, CA) | BRANAGH (OAKLAND, CA) | matched | M1b |
| different | BEK CONSULTING (DICKINSON, ND) | BEK CONSULTING (DICKINSON, ND) | matched | M1 |
| different | ARCHER DANIELS MIDLAND (DECATUR, IL) | ARCHER DANIELS MIDLAND (DECATUR, IL) | matched | M1 |
| different | HAGERMAN CONSTRUCTION (FISHERS, IN) | HAGERMAN (FISHERS, IN) | matched | M2 |
| different | BAINBRIDGE COMPANIES (WELLINGTON, FL) | BAINBRIDGE CONSTRUCTION (WELLINGTON, FL) | matched | M1b |
| different | SUNRUN (VISTA, CA) | SUNRUN (DUBLIN, CA) | matched | M1 |
| different | TIMELINE SERVICES (FIRESTONE, CO) | TIMELINE SERVICES HOLDINGS (ERIE, CO) | matched | M1b |
| different | PEGASUS LINK CONSTRUCTORS (DALLAS, TX) | PEGASUS LINK CONSTRUCTORS (DALLAS, TX) | matched | M1 |
| different | BOPAT ELECTRIC (FREDERICK, MD) | BOPAT ELECTRIC (COLUMBIA, MD) | matched | M1 |
| different | HOUCK (HARRISBURG, PA) | HOUCK SERVICES (HARRISBURG, PA) | matched | M1b |
| different | BOGNER CONSTRUCTION (WOOSTER, OH) | BOGNER (WOOSTER, OH) | matched | M1b |
