# Jev as the search (silver labels from ITA EINs): what the app's search misses

Seed 11, held out from the seed-7 set where the app's Jev thresholds were picked (no shared pair or search). Searches whose same-company record the app's search doesn't find or excludes, from 793 same-company pairs checked (one search per company). 30 searches (30 companies), each compared with every other record in a pool of 207 (6,180 pairs), with no blocking. Jev: `jev-latest` (served by jev-1.13.0). 242 s.

Found: how many records each finder would show the GC as a possible match. "Jev, the app's cut-offs" keeps a record unless P(same) ≤ 0.2 in the search's state or ≤ 0.06 in another, as the app does.

| Pairs | n | Rules (the app's search) | Jaro-Winkler ≥ 0.8 | Jev, the app's cut-offs | Jev P(same) > 0.2 | Jev P(same) ≥ 0.85 |
|---|---|---|---|---|---|---|
| Same company | 107 | 40 | 64 | 52 | 38 | 8 |
|   same name, same state | 8 | 8 | 8 | 8 | 8 | 4 |
|   same name, other state | 40 | 30 | 40 | 25 | 14 | 0 |
|   other name, same state | 19 | 2 | 8 | 11 | 11 | 4 |
|   other name, other state | 40 | 0 | 8 | 8 | 5 | 0 |
|   the rules don't find | 45 | 0 | 3 | 11 | 10 | 1 |
|   the rules exclude | 22 | 0 | 22 | 7 | 4 | 2 |
| Lookalike (same name core, other tax ID) | 20 | 6 | 12 | 5 | 2 | 0 |
| Other record | 6053 | 0 | 14 | 22 | 4 | 0 |

Ranking, Jaro-Winkler against Jev's P(same):

| | Jaro-Winkler | Jev |
|---|---|---|
| AUC, same company vs every other record | 0.827 | 0.859 |
| AUC, same company vs lookalikes | 0.58 | 0.599 |
| Same-company records ranked above every other company's record in their search | 0.523 | 0.477 |

Jev: 3,929,115 input tokens (≈ $0.1650), median 0.24 s a call, 0 calls failed.
At full size one search is 215,783 calls: about 137M input tokens (≈ $5.76 at list price) and 72 minutes at 12 parallel calls and this run's median 0.24 s a call. Jev kept 22 of 6,053 unrelated records here, about 784 a search at full size.

## Same company, found by Jev and not by the rules (18, first 15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| TK ELEVATOR RICHMOND (Ashland, VA) | THYSSENKRUPP ELEVATOR CORPORATION (Roanoke, VA) | 0.59 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | 107215 - THYSSENKRUPP ELEVATOR CORP (Lombard, IL) | 0.4 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | THYSSENKRUPP ELEVATOR CORPORATION (Fargo, ND) | 0.41 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | TK ELEVATOR CORPORATION (Livonia, MI) | 0.08 | 0.91 | excluded |
| TK ELEVATOR RICHMOND (Ashland, VA) | THYSSENKRUPP ELEVATOR CORPORATION (New York, NY) | 0.46 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | THYSSENKRUPP ELEVATOR CORP (Omaha, NE) | 0.38 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | THYSSENKRUPP ELEVATOR CORP (Honolulu, HI) | 0.3 | 0.47 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | TK ELEVATOR CORPORATION (King Of Prussia, PA) | 0.09 | 0.91 | excluded |
| TK ELEVATOR RICHMOND (Ashland, VA) | TK ELEVATOR CORPORATION (Hollins, VA) | 0.58 | 0.91 | excluded |
| FAIRFAX WATER (Fairfax, VA) | FAIRFAX COUNTY WATER AUTHORITY (Fairfax, VA) | 0.92 | 0.87 | excluded |
| J.T. VAUGHN CONSTRUCTION, LLC (Houston, TX) | VAUGHN CONSTRUCTION (Houston, TX) | 0.86 | 0.81 | excluded |
| BUILDERS SERVICES GROUP, INC. (North Las Vegas, NV) | BUILDERS SERVICES GROUP, INC. (Houston, TX) | 0.1 | 1.00 | excluded |
| POWER HOME SOLAR LLC (Chesterfield, MI) | POWERHOME SOLAR (Mooresville, NC) | 0.08 | 0.96 | not_found |
| JRCRUZ CORP. (Aberdeen, NJ) | JR CRUZ CORP. (Holmdel, NJ) | 0.76 | 0.96 | not_found |
| EDC (Midlothian, VA) | EILERSON DEVELOPMENT CORPORATION (Midlothian, VA) | 0.95 | 0.59 | not_found |

## Same company, found by the rules and not by Jev (6)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| 105887 - CECO CONCRETE CONSTRUCTION LLC (Andover, MN) | CECO CONCRETE CONSTRUCTION, L.L.C. (Tampa, FL) | 0.04 | 1.00 | matched |
| 105887 - CECO CONCRETE CONSTRUCTION LLC (Andover, MN) | CECO CONCRETE CONSTRUCTION (Olathe, KS) | 0.05 | 1.00 | matched |
| 105887 - CECO CONCRETE CONSTRUCTION LLC (Andover, MN) | CECO CONCRETE CONSTRUCTION (Metairie, LA) | 0.04 | 1.00 | matched |
| NORTH STAR LOGISTICS (Watford City, ND) | NORTH STAR LOGISTICS, LLC (Watertown, SD) | 0.02 | 1.00 | matched |
| NORTH STAR LOGISTICS (Watford City, ND) | NORTH STAR LOGISTICS, L.L.C. (Watertown, SD) | 0.04 | 1.00 | matched |
| STURGEON ELECTRIC COMPANY, INC. (Topeka, KS) | STURGEON ELECTRIC (Anchorage, AK) | 0.02 | 1.00 | uncertain |

## Same company, found by neither (49, first 15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| TK ELEVATOR RICHMOND (Ashland, VA) | TK ELEVATOR LAS VEGAS (Las Vegas, NV) | 0.01 | 0.83 | excluded |
| TK ELEVATOR RICHMOND (Ashland, VA) | WA317969555 - TK ELEVATOR CORPORATION (Atlanta, GA) | 0.05 | 0.91 | excluded |
| 317717935 - SOURCE REFRIGERATION & HVAC INC (Anaheim, CA) | COOLSYS, INC. (Boise, ID) | 0.0 | 0.41 | not_found |
| TECTA AMERICA LLC (Rosemont, IL) | EAGLE CORNICE CO., INC. (Cranston, RI) | 0.0 | 0.70 | not_found |
| TECTA AMERICA LLC (Rosemont, IL) | PRO-TEC ROOFING, INC. (Watertown, SD) | 0.01 | 0.51 | not_found |
| 105887 - CECO CONCRETE CONSTRUCTION LLC (Andover, MN) | TRIBCO CONSTRUCTION SERVICES, LLC (Chicago, IL) | 0.0 | 0.68 | not_found |
| TESLA INC. (Draper, UT) | SOLARCITY CORPORATION (Norwell, MA) | 0.0 | 0.64 | not_found |
| BLUE SKY CONTROLS (Pittsburgh, PA) | HATZEL & BUEHLER INC (Livonia, MI) | 0.0 | 0.49 | not_found |
| BLUE SKY CONTROLS (Pittsburgh, PA) | HATZEL & BUEHLER, INC. (Pittsburgh, PA) | 0.04 | 0.49 | not_found |
| BLUE SKY CONTROLS (Pittsburgh, PA) | HATZEL & BUEHLER, INC. (Philadelphia, PA) | 0.01 | 0.49 | not_found |
| BLUE SKY CONTROLS (Pittsburgh, PA) | HATZEL & BUEHLER, INC. (Philadelphia, PA) | 0.01 | 0.49 | not_found |
| BLUE SKY CONTROLS (Pittsburgh, PA) | HATZEL & BUEHLER INC (Beltsville, MD) | 0.0 | 0.49 | not_found |
| LENNAR-SOUTHWEST FLORIDA (Fort Myers, FL) | LENNAR COLORADO LLC (Englewood, CO) | 0.0 | 0.87 | excluded |
| LENNAR-SOUTHWEST FLORIDA (Fort Myers, FL) | LENNAR - IDAHO BOISE (Eagle, ID) | 0.0 | 0.83 | excluded |
| LENNAR-SOUTHWEST FLORIDA (Fort Myers, FL) | LENNAR RENO, LLC (Reno, NV) | 0.0 | 0.69 | not_found |

## Different companies Jev rates highest (15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| GRANITE CONSTRUCTION COMPANY (Sparks, NV) | GRANITE CONSTRUCTION COMPANY (Watsonville, CA) | 0.32 | 1.00 | uncertain |
| EDC (Midlothian, VA) | EDGE CONSTRUCTION USA, INC. (Fort Lauderdale, FL) | 0.23 | 0.77 | not_found |
| EDC (Midlothian, VA) | EDGE CONSTRUCTION USA, INC. (Fort Lauderdale, FL) | 0.23 | 0.77 | not_found |
| EDC (Midlothian, VA) | THE EDGE CONSTRUCTION COMPANY, INC. (Bartlett, IL) | 0.22 | 0.78 | not_found |
| TECTA AMERICA LLC (Rosemont, IL) | TECTA AMERICA CORP. (Santa Ana, CA) | 0.21 | 1.00 | matched |
| TK ELEVATOR RICHMOND (Ashland, VA) | TECTA AMERICA CORP. (Santa Ana, CA) | 0.21 | 0.62 | not_found |
| TECTA AMERICA LLC (Rosemont, IL) | ROOFING SERVICES AND SOLUTIONS, A TECTA AMERICA COMPANY, LLC (Saint Louis, MO) | 0.2 | 0.49 | uncertain |
| EDC (Midlothian, VA) | EDGE COMMERCIAL, LLC. (Grimes, IA) | 0.18 | 0.79 | not_found |
| EDC (Midlothian, VA) | EDGE COMMERCIAL, LLC. (Grimes, IA) | 0.18 | 0.79 | not_found |
| BALFOUR BEATTY INFRASTRUCTURE INC. (Suffolk, VA) | 76387 - EDC (Midlothian, VA) | 0.17 | 0.46 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | THOMPSON SUSKIND, L.P. (San Francisco, CA) | 0.16 | 0.50 | not_found |
| TK ELEVATOR RICHMOND (Ashland, VA) | TECTA AMERICA LLC (Rosemont, IL) | 0.15 | 0.62 | not_found |
| STURGEON ELECTRIC COMPANY, INC. (Topeka, KS) | STURGEON ELECTRIC COMPANY, INC. (Phoenix, AZ) | 0.15 | 1.00 | matched |
| EDC (Midlothian, VA) | CECO CONCRETE CONSTRUCTION, LLC. (Overland Park, KS) | 0.14 | 0.41 | not_found |
| EDC (Midlothian, VA) | EDGE CONSTRUCTION LLC (Draper, UT) | 0.14 | 0.78 | not_found |

Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, and a record under another name with the same tax ID can't be found from a name at all. Read the lists before trusting a small difference.
