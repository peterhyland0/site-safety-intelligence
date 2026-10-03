# Adjudicator comparison (silver labels from ITA EINs)

Seed 7: the development set, where Jev's tuned thresholds were picked.

2400 silver pairs; the rules leave **302** uncertain (87 same company, 215 different). Those go to each adjudicator with the packet the app would build. 46 carry red flags (the app asks the GC about those whatever the AI says). 1 s.

Models: llm: `deepseek-ai/DeepSeek-V4.1-Flash`, jev: `jev-latest` (Jev served by jev-1.13.0).

| | Rules only | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|
| Wrong merges (of 215 different) | 0 | 1 | 0 | 0 | 0 |
| Wrong exclusions (of 87 same) | 0 | 9 | 16 | 3 | 22 |
| Same company matched (of 87) | 0 | 1 | 0 | 0 | 0 |
| Different company excluded (of 215) | 0 | 137 | 160 | 154 | 165 |
| Resolved (share not left possible) | 0.0 | 0.49 | 0.583 | 0.52 | 0.619 |
| Precision of matches | None | 0.5 | None | None | None |
| Precision of exclusions | None | 0.938 | 0.909 | 0.981 | 0.882 |
| AUC of P(same) | 0.5 | 0.804 | 0.845 | 0.845 | 0.83 |
| Brier score of P(same) (lower is better) | 0.25 | 0.161 | 0.181 | 0.181 | 0.174 |
| Answers rejected by validation | 0 | 6 | 0 | 0 | 0 |
| Answers missing (call failed) | 0 | 0 | 0 | 0 | 0 |
| Median seconds per packet | None | 0.89 | 0.25 | 0.25 | 0.25 |
| p90 seconds per packet | None | 1.38 | 0.31 | 0.31 | 0.31 |

Tokens: LLM 240,675 (in + out); Jev 379,359 input (≈ $0.0159 at list price; output is free).

Thresholds are the app's (`adjudicate.ai_bucket`): same ≥ 0.85 → matched, different ≥ 0.80 → excluded. "Jev choice, tuned" uses the choice's P(same) instead: excluded at ≤ 0.2 in the sub's state and ≤ 0.06 in another, matched at ≥ 0.85.

## What the rules do with each pair type

Only the uncertain ones reach the adjudicator.

| Pairs | matched | uncertain | excluded | not found | matched by rule |
|---|---|---|---|---|---|
| Same company, same name | 285 | 81 | 2 | 0 | M1 142, M3 143 |
| Same company, other name | 5 | 6 | 7 | 14 | M1 1, M1b 2, M2 2 |
| Different company, same name, same state | 23 | 3 | 0 | 0 | M1 23 |
| Different company, same name core, same state | 22 | 108 | 244 | 0 | M1b 16, M2 6 |
| Different company, same name core, other state | 51 | 104 | 1441 | 4 | M3 51 |

## By label and place

Outcomes as matched · possible · excluded. The other-state different companies are two local firms (each tax ID files in one state), so a national firm's own namesakes aren't among them.

| Pairs | n | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|
| Same company, same state | 21 | 1 · 19 · 1 | 0 · 20 · 1 | 0 · 20 · 1 | 0 · 20 · 1 |
| Same company, other state | 66 | 0 · 58 · 8 | 0 · 51 · 15 | 0 · 64 · 2 | 0 · 45 · 21 |
| Different company, same state | 111 | 1 · 57 · 53 | 0 · 44 · 67 | 0 · 32 · 79 | 0 · 42 · 69 |
| Different company, other state | 104 | 0 · 20 · 84 | 0 · 11 · 93 | 0 · 29 · 75 | 0 · 8 · 96 |

## Matching at other thresholds

Matched if P(same) ≥ t: same-company records matched / different-company records matched.

| t | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev yes/no |
|---|---|---|---|
| 0.95 | 0/87 · 0 | 0/87 · 0 | 0/87 · 0 |
| 0.9 | 1/87 · 0 | 0/87 · 0 | 0/87 · 0 |
| 0.85 | 1/87 · 1 | 0/87 · 0 | 0/87 · 0 |
| 0.8 | 3/87 · 2 | 0/87 · 0 | 0/87 · 0 |
| 0.7 | 8/87 · 9 | 3/87 · 0 | 0/87 · 0 |
| 0.6 | 8/87 · 10 | 6/87 · 1 | 4/87 · 0 |

## LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash): disagreements with the silver label (10, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | TURNER CONSTRUCTION (RESTON, VA) | TURNER CONSTRUCTION (CHICAGO, IL) | different 0.85: The sub and matched records are in RESTON VA (E1-E3), while the candidate is in CHICAGO IL with no shared address (E4); a common name in a different state is usually a different company, and the differing trade codes (2362 vs 2361) further separate them. |
| same | PERFORMANCE CONTRACTING (GRANDVIEW, MO) | PERFORMANCE CONTRACTING (TEMPE, AZ) | different 0.80: The matched record is in Grandview, MO (E1, E2), while the candidate is in Tempe, AZ, with a different trade code (2381 vs 2383) and no shared address (E3). |
| same | PAR ELECTRICAL CONTRACTORS (KANSAS CITY, MO) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different 0.90: The sub and matched OSHA records are in Kansas City, MO (E1-E3), while all candidates are at unrelated California addresses in Vacaville, Escondido, and Rancho Cucamonga (E4-E6), with no shared location and a different trade code (2382 vs 2371). |
| same | NPL CONSTRUCTION (TULSA, OK) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.85: The sub is in Tulsa, OK (E1, E2), while the candidates are both in Las Vegas, NV (E3, E4) with no shared address, and 'NPL CONSTRUCTION' is a confusable name without a company ID. Same trade code alone is weak. |
| same | HELIX ELECTRIC (OAKLAND, CA) | HELIX ELECTRIC (MANASSAS, VA) | different 0.85: The sub and the matched record are in Oakland, CA, while the candidate 'HELIX ELECTRIC' is at a Manassas, VA address with different trade codes (2382 vs 2389), so it is a different company despite the identical name. |
| same | PERFORMANCE CONTRACTING (PORTLAND, OR) | PERFORMANCE CONTRACTING (CARMEL, IN) | different 0.85: The sub and the already-matched record are in Portland, OR (E1, E2), while the candidate is in Carmel, IN with a different trade code (2381 vs 2383) and no shared address (E3). A common name in a different state with no shared location is a different company. |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | different 0.80: The sub and its matched record are in Jackson, WY (E1, E2), while the candidate is in Del Valle, TX with no shared address and a different trade code (2381 vs 2383) (E3). |
| same | PAR ELECTRICAL CONTRACTORS (ESCONDIDO, CA) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different 0.80: The sub's matched records are at 525 Corporate Dr, Escondido (E2), while the candidates are at Vacaville (E4) and Rancho Cucamonga (E5) with no shared address; the identical generic name and trade code alone are insufficient to link them. |
| same | SAK CONSTRUCTION (ROCKLIN, CA) | SAK CONSTRUCTION (O FALLON, MO) | different 0.85: The sub is in ROCKLIN, CA (E1, E2), while the candidate is in O FALLON, MO with no shared address (E3); a common name in a different state is usually a different company. |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | same 0.85: Candidates 'BONE DRY ROOFING' share the exact street address 7735 WINTON DR (E5, plus the WONTON DR typo variant E6) with the sub's already-matched record at the same Indianapolis address and same trade code 2381 (E2). |

## Jev choice: disagreements with the silver label (16, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | NVR (BRECKSVILLE, OH) | NVR (BLUE BELL, PA) | different 0.85 (P(same) 0.09) |
| same | PAR ELECTRICAL CONTRACTORS (KANSAS CITY, MO) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different 0.94 (P(same) 0.04) |
| same | CAMP CONSTRUCTION SERVICES (HOUSTON, TX) | CAMP ROOFING (HOUSTON, TX) | different 0.94 (P(same) 0.04) |
| same | WCA GROUP (CARMEL, IN) | WCA GROUP (FAIRFIELD, OH) | different 0.82 (P(same) 0.10) |
| same | TURNER CONSTRUCTION (ANAHEIM, CA) | TURNER CONSTRUCTION (KANSAS CITY, MO) | different 0.83 (P(same) 0.09) |
| same | SUNRUN INSTALLATION SERVICES (LEHI, UT) | SUNRUN (MARLBOROUGH, MA) | different 0.87 (P(same) 0.08) |
| same | FL CRANE SONS (MEMPHIS, TN) | FL CRANE SONS (FULTON, MS) | different 0.89 (P(same) 0.06) |
| same | NPL CONSTRUCTION (TULSA, OK) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.86 (P(same) 0.07) |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | different 0.85 (P(same) 0.07) |
| same | SUNRUN INSTALLATION SERVICES (SOMERSET, NJ) | SUNRUN (MARLBOROUGH, MA) | different 0.89 (P(same) 0.07) |
| same | NVR (HUNTERSVILLE, NC) | NVR (LANHAM, MD) | different 0.93 (P(same) 0.04) |
| same | NVR (SPRINGBORO, OH) | NVR (BALTIMORE, MD) | different 0.82 (P(same) 0.14) |
| same | NVR (PITTSBURGH, PA) | NVR (NOTTINGHAM, MD) | different 0.88 (P(same) 0.09) |
| same | NVR (FRANKLIN, TN) | NVR (LANHAM, MD) | different 0.83 (P(same) 0.11) |
| same | SAK CONSTRUCTION (ROCKLIN, CA) | SAK CONSTRUCTION (O FALLON, MO) | different 0.85 (P(same) 0.08) |

## Jev choice, tuned: disagreements with the silver label (3, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | PAR ELECTRICAL CONTRACTORS (KANSAS CITY, MO) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | P(same) 0.04, excluded at ≤ 0.06 |
| same | CAMP CONSTRUCTION SERVICES (HOUSTON, TX) | CAMP ROOFING (HOUSTON, TX) | P(same) 0.04, excluded at ≤ 0.2 |
| same | NVR (HUNTERSVILLE, NC) | NVR (LANHAM, MD) | P(same) 0.04, excluded at ≤ 0.06 |

## Jev yes/no: disagreements with the silver label (22, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | NVR (BRECKSVILLE, OH) | NVR (BLUE BELL, PA) | different 0.84 (P(same) 0.16) |
| same | MOSS ASSOCIATES (FORT LAUDERDALE, FL) | MOSS ASSOCIATES (EL PASO, TX) | different 0.80 (P(same) 0.20) |
| same | PAR ELECTRICAL CONTRACTORS (KANSAS CITY, MO) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different 0.86 (P(same) 0.14) |
| same | CAMP CONSTRUCTION SERVICES (HOUSTON, TX) | CAMP ROOFING (HOUSTON, TX) | different 0.82 (P(same) 0.18) |
| same | WCA GROUP (CARMEL, IN) | WCA GROUP (FAIRFIELD, OH) | different 0.84 (P(same) 0.16) |
| same | TURNER CONSTRUCTION (ANAHEIM, CA) | TURNER CONSTRUCTION (KANSAS CITY, MO) | different 0.80 (P(same) 0.20) |
| same | SUNRUN INSTALLATION SERVICES (LEHI, UT) | SUNRUN (MARLBOROUGH, MA) | different 0.80 (P(same) 0.20) |
| same | FL CRANE SONS (MEMPHIS, TN) | FL CRANE SONS (FULTON, MS) | different 0.83 (P(same) 0.17) |
| same | NPL CONSTRUCTION (TULSA, OK) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.85 (P(same) 0.15) |
| same | PERFORMANCE CONTRACTING (KENNESAW, GA) | PERFORMANCE CONTRACTING (LAKELAND, FL) | different 0.80 (P(same) 0.20) |
| same | HELIX ELECTRIC (OAKLAND, CA) | HELIX ELECTRIC (MANASSAS, VA) | different 0.80 (P(same) 0.20) |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | different 0.81 (P(same) 0.19) |
| same | SUNRUN INSTALLATION SERVICES (SOMERSET, NJ) | SUNRUN (MARLBOROUGH, MA) | different 0.80 (P(same) 0.20) |
| same | NVR (HUNTERSVILLE, NC) | NVR (LANHAM, MD) | different 0.84 (P(same) 0.16) |
| same | PERFORMANCE CONTRACTING (ANAHEIM, CA) | PERFORMANCE CONTRACTING (WOODINVILLE, WA) | different 0.80 (P(same) 0.20) |

Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, so some "disagreements" are label errors. Read them before trusting a small difference.
