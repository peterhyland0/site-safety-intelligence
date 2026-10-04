# Adjudicator comparison (silver labels from ITA EINs)

Seed 7: the development set, where the app's Jev thresholds were picked.

2400 silver pairs; the rules leave **302** uncertain (87 same company, 215 different). Those go to each adjudicator with the packet the app would build. 46 carry red flags (the app asks the GC about those whatever the AI says). 8 s.

Models: llm: `deepseek-ai/DeepSeek-V4.1-Flash`, llm:glm-5.3: `zai-org/GLM-5.3`, llm:kimi-k3: `moonshotai/Kimi-K3`, jev: `jev-latest` (Jev served by jev-1.13.0).

| | Rules only | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | glm-5.3 | kimi-k3 | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|---|---|
| Wrong merges (of 215 different) | 0 | 1 | 1 | 3 | 0 | 0 | 0 |
| Wrong exclusions (of 87 same) | 0 | 9 | 0 | 3 | 16 | 3 | 22 |
| Same company matched (of 87) | 0 | 1 | 1 | 4 | 0 | 0 | 0 |
| Different company excluded (of 215) | 0 | 137 | 114 | 119 | 160 | 154 | 165 |
| Resolved (share not left possible) | 0.0 | 0.49 | 0.384 | 0.427 | 0.583 | 0.52 | 0.619 |
| Precision of matches | None | 0.5 | 0.5 | 0.571 | None | None | None |
| Precision of exclusions | None | 0.938 | 1.0 | 0.975 | 0.909 | 0.981 | 0.882 |
| AUC of P(same) | 0.5 | 0.804 | 0.894 | 0.867 | 0.845 | 0.845 | 0.83 |
| Brier score of P(same) (lower is better) | 0.25 | 0.161 | 0.132 | 0.139 | 0.181 | 0.181 | 0.174 |
| Answers rejected by validation | 0 | 6 | 27 | 38 | 0 | 0 | 0 |
| Answers missing (call failed) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Median seconds per packet | None | 0.89 | 3.79 | 11.76 | 0.25 | 0.25 | 0.25 |
| p90 seconds per packet | None | 1.38 | 26.19 | 24.73 | 0.31 | 0.31 | 0.31 |

Tokens: LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) 209,888 in, 30,787 out; glm-5.3 215,386 in, 489,114 out; kimi-k3 236,517 in, 129,458 out; Jev 379,359 input (≈ $0.0159 at list price; output is free).

Thresholds are the app's (`adjudicate.ai_bucket`): same ≥ 0.85 → matched, different ≥ 0.80 → excluded. "Jev choice, tuned" is what the app does with Jev (`ssi.llm.jev.decision`): the choice's P(same), excluded at ≤ 0.2 in the sub's state and ≤ 0.06 in another, matched at ≥ 0.85.

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

| Pairs | n | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | glm-5.3 | kimi-k3 | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|---|---|
| Same company, same state | 21 | 1 · 19 · 1 | 1 · 20 · 0 | 3 · 18 · 0 | 0 · 20 · 1 | 0 · 20 · 1 | 0 · 20 · 1 |
| Same company, other state | 66 | 0 · 58 · 8 | 0 · 66 · 0 | 1 · 62 · 3 | 0 · 51 · 15 | 0 · 64 · 2 | 0 · 45 · 21 |
| Different company, same state | 111 | 1 · 57 · 53 | 1 · 71 · 39 | 3 · 61 · 47 | 0 · 44 · 67 | 0 · 32 · 79 | 0 · 42 · 69 |
| Different company, other state | 104 | 0 · 20 · 84 | 0 · 29 · 75 | 0 · 32 · 72 | 0 · 11 · 93 | 0 · 29 · 75 | 0 · 8 · 96 |

## Matching at other thresholds

Matched if P(same) ≥ t: same-company records matched / different-company records matched.

| t | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | glm-5.3 | kimi-k3 | Jev choice | Jev yes/no |
|---|---|---|---|---|---|
| 0.95 | 0/87 · 0 | 1/87 · 0 | 0/87 · 0 | 0/87 · 0 | 0/87 · 0 |
| 0.9 | 1/87 · 0 | 1/87 · 0 | 2/87 · 1 | 0/87 · 0 | 0/87 · 0 |
| 0.85 | 1/87 · 1 | 1/87 · 1 | 4/87 · 3 | 0/87 · 0 | 0/87 · 0 |
| 0.8 | 3/87 · 2 | 3/87 · 1 | 6/87 · 3 | 0/87 · 0 | 0/87 · 0 |
| 0.7 | 8/87 · 9 | 19/87 · 6 | 14/87 · 5 | 3/87 · 0 | 0/87 · 0 |
| 0.6 | 8/87 · 10 | 25/87 · 11 | 20/87 · 10 | 6/87 · 1 | 4/87 · 0 |

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

## glm-5.3: disagreements with the silver label (1, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| different | WRIGHT BROTHERS CONTRACTING (CHARLESTON, TN) | WRIGHT BROTHERS CONSTRUCTION (CHARLESTON, TN) | same 0.85: The candidate 'WRIGHT BROTHERS CONSTRUCTION' exactly matches the already-matched E2 record name in Charleston TN 37310, with its 2017-12-13 activity falling inside E2's 2017-2022 active period; the PO BOX 427 vs 437 difference looks like a digit transposition rather than a different address. |

## kimi-k3: disagreements with the silver label (6, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | PERFORMANCE CONTRACTING (GRANDVIEW, MO) | PERFORMANCE CONTRACTING (TEMPE, AZ) | different 0.85: The matched records place the sub at Grandview, MO with trade code 2383 active 2017-2020, while the candidate is at a Tempe, AZ address with trade code 2381 active 2023-2024. A common name in a different state with no shared address, no overlapping years, and a different trade code is usually a different company. |
| same | PERFORMANCE CONTRACTING (PORTLAND, OR) | PERFORMANCE CONTRACTING (CARMEL, IN) | different 0.85: The matched OSHA record (E2) is at Portland, OR with trade code 2383, matching the sub's Portland, OR location (E1). The candidate (E3) is in Carmel, IN with a different trade code (2381) and no shared address; 'Performance Contracting' is a common name appearing in a different state, indicating a different company. |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | different 0.82: The name 'STANDARD DRYWALL' is common, and the candidate is in DEL VALLE TX with a different trade code (2381) while the sub and its matched record are in JACKSON WY with trade code 2383; with no shared address and a different state, this is likely a different company. |
| different | GUY M TURNER (GREENSBORO, NC) | GUY M TURNER CRANE RIGGING (GREENSBORO, NC) | same 0.90: The candidate 'GUY M TURNER CRANE RIGGING' shares the exact address 4514 S HOLDEN RD, GREENSBORO NC 27406, the same trade code 2389, and overlapping years with the already matched record E2; 'CRANE RIGGING' is a business descriptor, not a location/project suffix, so this is a name variant of the same company. |
| different | FLY FORM STRUCTURES (ATLANTA, GA) | FLY FORM CONCRETE STRUCTURES (ATLANTA, GA) | same 0.85: The candidate FLY FORM CONCRETE STRUCTURES shares the exact address (1817 WESTGATE PKWY, ATLANTA GA 30336) and trade code 2381 with the already-matched FLY FORM STRUCTURES, and its 2023 activity follows the matched record's 2017–2022 span. The added word 'CONCRETE' is a spelling variant rather than evidence of a sister company. |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | same 0.85: E4 shares the exact address 7735 WINTON DR with already-matched E2, and all candidates are in INDIANAPOLIS with the same trade code 2381 as E2/E3, so the missing 'COMMERCIAL' is just a name variant; E5's 'WONTON DR' is an obvious typo of the same address and E6 is another site in the same city. |

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
| same | PAR ELECTRICAL CONTRACTORS (KANSAS CITY, MO) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different (P(same) 0.04) |
| same | CAMP CONSTRUCTION SERVICES (HOUSTON, TX) | CAMP ROOFING (HOUSTON, TX) | different (P(same) 0.04) |
| same | NVR (HUNTERSVILLE, NC) | NVR (LANHAM, MD) | different (P(same) 0.04) |

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
