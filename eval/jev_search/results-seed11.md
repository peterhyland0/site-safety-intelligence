# Jev as the search (silver labels from ITA EINs)

Seed 11, held out from the seed-7 set where the app's Jev thresholds were picked (no shared pair or search). 60 searches (60 companies), each compared with every other record in a pool of 384 (22,980 pairs), with no blocking. Jev: `jev-latest` (served by jev-1.13.0). 473 s.

Found: how many records each finder would show the GC as a possible match. "Jev, the app's cut-offs" keeps a record unless P(same) ≤ 0.2 in the search's state or ≤ 0.06 in another, as the app does.

| Pairs | n | Rules (the app's search) | Jaro-Winkler ≥ 0.8 | Jev, the app's cut-offs | Jev P(same) > 0.2 | Jev P(same) ≥ 0.85 |
|---|---|---|---|---|---|---|
| Same company | 161 | 149 | 154 | 134 | 104 | 25 |
|   same name, same state | 36 | 36 | 36 | 36 | 36 | 25 |
|   same name, other state | 102 | 102 | 102 | 81 | 55 | 0 |
|   other name, same state | 8 | 6 | 7 | 8 | 8 | 0 |
|   other name, other state | 15 | 5 | 9 | 9 | 5 | 0 |
|   the rules don't find | 7 | 0 | 0 | 6 | 6 | 0 |
|   the rules exclude | 5 | 0 | 5 | 3 | 1 | 0 |
| Lookalike (same name core, other tax ID) | 138 | 38 | 83 | 34 | 28 | 2 |
| Other record | 22681 | 0 | 90 | 14 | 0 | 0 |

Ranking, Jaro-Winkler against Jev's P(same):

| | Jaro-Winkler | Jev |
|---|---|---|
| AUC, same company vs every other record | 0.963 | 0.995 |
| AUC, same company vs lookalikes | 0.88 | 0.844 |
| Same-company records ranked above every other company's record in their search | 0.783 | 0.745 |

Jev: 14,787,065 input tokens (≈ $0.6211), median 0.241 s a call, 0 calls failed.
At full size one search is 215,783 calls: about 139M input tokens (≈ $5.83 at list price) and 72 minutes at 12 parallel calls and this run's median 0.241 s a call. Jev kept 14 of 22,681 unrelated records here, about 133 a search at full size.

## Same company, found by Jev and not by the rules (9)

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

## Same company, found by the rules and not by Jev (24, first 15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| TRI POINTE HOMES, INC. (Irvine, CA) | 158618 - TRI POINTE HOMES HOLDINGS, INC. (Charlotte, NC) | 0.05 | 0.93 | matched |
| TRI POINTE HOMES, INC. (Irvine, CA) | 154604 - TRI POINTE HOMES HOLDINGS, INC (Charlotte, NC) | 0.06 | 0.93 | matched |
| TRI POINTE HOMES, INC. (Irvine, CA) | 151956 - TRI POINTE HOMES HOLDINGS, INC. (Charlotte, NC) | 0.06 | 0.93 | matched |
| PENHALL COMPANY (Aiea, HI) | 161974 - PENHALL COMPANY (Greer, SC) | 0.05 | 1.00 | matched |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | 317727255 - PERFORMANCE CONTRACTING INC (Portland, OR) | 0.02 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | 110860 - PERFORMANCE CONTRACTING INC (Carmel, IN) | 0.04 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING INC. (Exton, PA) | 0.04 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING, INC. (Pasadena, TX) | 0.01 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING INC. (North Highlands, CA) | 0.01 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING, INC. (Grandview, MO) | 0.05 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING, INC. (Lake Zurich, IL) | 0.04 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING INC. (Las Vegas, NV) | 0.03 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | URX2023XT3633X0087 - PERFORMANCE CONTRACTING, INC. (Tempe, AZ) | 0.05 | 1.00 | uncertain |
| 61178 - PERFORMANCE CONTRACTING INC (Calvert City, KY) | PERFORMANCE CONTRACTING, INC. (Benicia, CA) | 0.05 | 1.00 | uncertain |
| CENTIMARK CORPORATION (Hazelwood, MO) | CENTIMARK CORPORATION (Franklin, OH) | 0.05 | 1.00 | matched |

## Same company, found by neither (3)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| TK ELEVATOR RICHMOND (Ashland, VA) | TK ELEVATOR LAS VEGAS (Las Vegas, NV) | 0.01 | 0.83 | excluded |
| TK ELEVATOR RICHMOND (Ashland, VA) | WA317969555 - TK ELEVATOR CORPORATION (Atlanta, GA) | 0.05 | 0.91 | excluded |
| 317717935 - SOURCE REFRIGERATION & HVAC INC (Anaheim, CA) | COOLSYS, INC. (Boise, ID) | 0.0 | 0.41 | not_found |

## Different companies Jev rates highest (15)

| Search | Record | Jev P(same) | Jaro-Winkler | Rules |
|---|---|---|---|---|
| PEGASUS LINK CONSTRUCTORS (Dallas, TX) | PEGASUS LINK CONSTRUCTORS (Dallas, TX) | 0.97 | 1.00 | matched |
| 158992 - ARISTEO CONSTRUCTION COMPANY (Livonia, MI) | ARISTEO (Livonia, MI) | 0.91 | 0.87 | matched |
| ST. CLOUD REFRIGERATION, INC. (Saint Cloud, MN) | 105965 - ST CLOUD REFRIGERATION INC (Baxter, MN) | 0.74 | 1.00 | matched |
| OUTSOURCE UTILITY CONTRACTOR, LLC (Torrance, CA) | OUTSOURCE LLC (El Segundo, CA) | 0.62 | 0.86 | uncertain |
| 109192 - GRAYCOR INDUSTRIAL CONSTRUCTORS (Villa Park, IL) | GRAYCOR CONSTRUCTION COMPANY, INC. (Oakbrook Terrace, IL) | 0.61 | 0.89 | uncertain |
| 109192 - GRAYCOR INDUSTRIAL CONSTRUCTORS (Villa Park, IL) | GRAYCOR CONSTRUCTION COMPANY INC. (Oakbrook Terrace, IL) | 0.59 | 0.89 | uncertain |
| D.R. HORTON INC. (Orlando, FL) | D.R. HORTON (San Antonio, TX) | 0.56 | 1.00 | matched |
| D.R. HORTON INC. (Orlando, FL) | D R HORTON INC. (Austin, TX) | 0.54 | 1.00 | matched |
| D.R. HORTON INC. (Orlando, FL) | 139949 - D. R. HORTON, INC. (Raleigh, NC) | 0.48 | 1.00 | matched |
| D.R. HORTON INC. (Orlando, FL) | D.R. HORTON (Oklahoma City, OK) | 0.47 | 1.00 | matched |
| OUTSOURCE UTILITY CONTRACTOR, LLC (Torrance, CA) | OUTSOURCE LLC (El Segundo, CA) | 0.47 | 0.86 | uncertain |
| D.R. HORTON INC. (Orlando, FL) | D.R. HORTON, INC. (Albuquerque, NM) | 0.44 | 1.00 | matched |
| WA317945094 - OMNI CONTRACTING SOLUTIONS LLC (Everett, WA) | WA317992319 - OMNI CONCRETE SOLUTIONS LLC (Everett, WA) | 0.43 | 0.90 | uncertain |
| D.R. HORTON INC. (Orlando, FL) | D.R. HORTON, INC. (Mason, OH) | 0.43 | 1.00 | matched |
| D.R. HORTON INC. (Orlando, FL) | D.R. HORTON, INC. (Mount Laurel, NJ) | 0.39 | 1.00 | matched |

Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, and a record under another name with the same tax ID can't be found from a name at all. Read the lists before trusting a small difference.
