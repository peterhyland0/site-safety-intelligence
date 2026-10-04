# Jev as the search (silver labels from ITA EINs)

Seed 7, the set where the app's Jev thresholds were picked. 10 searches (10 companies), each compared with every other record in a pool of 120 (1,190 pairs), with no blocking. Jev: `jev-latest` (served by jev-1.13.0). 2 s.

Found: how many records each finder would show the GC as a possible match. "Jev, the app's cut-offs" keeps a record unless P(same) ≤ 0.2 in the search's state or ≤ 0.06 in another, as the app does.

| Pairs | n | Rules (the app's search) | Jaro-Winkler ≥ 0.8 | Jev, the app's cut-offs | Jev P(same) > 0.2 | Jev P(same) ≥ 0.85 |
|---|---|---|---|---|---|---|
| Same company | 26 | 26 | 26 | 26 | 25 | 6 |
|   same name, same state | 5 | 5 | 5 | 5 | 5 | 4 |
|   same name, other state | 19 | 19 | 19 | 19 | 18 | 0 |
|   other name, same state | 2 | 2 | 2 | 2 | 2 | 2 |
| Lookalike (same name core, other tax ID) | 34 | 5 | 27 | 3 | 2 | 0 |
| Other record | 1130 | 0 | 3 | 1 | 0 | 0 |

Ranking, Jaro-Winkler against Jev's P(same):

| | Jaro-Winkler | Jev |
|---|---|---|
| AUC, same company vs every other record | 1.0 | 0.999 |
| AUC, same company vs lookalikes | 0.998 | 0.957 |
| Same-company records ranked above every other company's record in their search | 0.923 | 0.654 |

Jev: 760,582 input tokens (≈ $0.0319), median 0.242 s a call, 0 calls failed.
At full size one search is 215,783 calls: about 138M input tokens (≈ $5.79 at list price) and 109 minutes at 8 parallel calls and this run's median 0.242 s a call. Jev kept 1 of 1,130 unrelated records here, about 191 a search at full size.

## Same company, found by Jev and not by the rules (0)

## Same company, found by the rules and not by Jev (0)

## Same company, found by neither (0)

## Different companies Jev rates highest (15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| HENSEL PHELPS CONSTRUCTION COMPANY (Leesburg, VA) | HENSEL PHELPS (Honolulu, HI) | 0.46 | 0.90 | matched |
| AMX COOLING & HEATING, LLC (Pleasantville, NY) | AMX MECHANICAL CORP. (Pleasantville, NY) | 0.45 | 0.70 | uncertain |
| TURNER CONSTRUCTION COMPANY (Reston, VA) | TECTA AMERICA EAST LLC (Fruitland, MD) | 0.08 | 0.56 | not_found |
| TURNER CONSTRUCTION COMPANY (Reston, VA) | TURNER INDUSTRIES GROUP, L.L.C. (Corpus Christi, TX) | 0.07 | 0.83 | excluded |
| ALL TEXAS ELECTRICAL CONTRACTORS INC (Houston, TX) | TECTA AMERICA EAST LLC (Fruitland, MD) | 0.06 | 0.69 | not_found |
| MITCHELL CONCRETE (Rancho Cordova, CA) | MITCHELL ENGINEERING (San Francisco, CA) | 0.05 | 0.87 | excluded |
| 103264 - EGAN COMPANY (Champlin, MN) | EGAN CONSTRUCTION LLC (Kingsport, TN) | 0.04 | 0.85 | uncertain |
| MITCHELL CONCRETE (Rancho Cordova, CA) | ASPHALT AND CONCRETE ENTERPRISES INC. (Santee, CA) | 0.04 | 0.59 | not_found |
| JRC MECHANICAL, LLC (Chesapeake, VA) | ENERGY ONE AMERICA (Chesapeake, VA) | 0.04 | 0.64 | not_found |
| TURNER CONSTRUCTION COMPANY (Reston, VA) | TURNER INDUSTRIES GROUP, L.L.C. (Pasadena, TX) | 0.04 | 0.83 | excluded |
| PERFORMANCE ROOFING, LLC (Oviedo, FL) | PERFORMANCE CONTRACTING, INC (Lakeland, FL) | 0.04 | 0.90 | excluded |
| TURNER CONSTRUCTION COMPANY (Reston, VA) | TURNER INDUSTRIES GROUP, LLC (Baton Rouge, LA) | 0.04 | 0.83 | excluded |
| HENSEL PHELPS CONSTRUCTION COMPANY (Leesburg, VA) | CPF INC. (Prince Frederick, MD) | 0.03 | 0.46 | not_found |
| 103264 - EGAN COMPANY (Champlin, MN) | PERFORMANCE INSTALLATION (Englewood, CO) | 0.03 | 0.62 | not_found |
| COLLINS PLUMBING, INC. (El Cajon, CA) | CPF INC. (Prince Frederick, MD) | 0.03 | 0.60 | not_found |

Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, and a record under another name with the same tax ID can't be found from a name at all. Read the lists before trusting a small difference.
