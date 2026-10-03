# Adjudicator comparison (silver labels from ITA EINs)

Seed 11: held out from the seed-7 development set (no shared pair or search), so Jev's tuned thresholds were fixed before this sample was drawn.

1931 silver pairs; the rules leave **246** uncertain (74 same company, 172 different). Those go to each adjudicator with the packet the app would build. 23 carry red flags (the app asks the GC about those whatever the AI says). 803 s.

Models: llm: `deepseek-ai/DeepSeek-V4.1-Flash`, jev: `jev-latest` (Jev served by jev-1.13.0).

| | Rules only | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|
| Wrong merges (of 172 different) | 0 | 2 | 0 | 0 | 0 |
| Wrong exclusions (of 74 same) | 0 | 13 | 17 | 9 | 26 |
| Same company matched (of 74) | 0 | 4 | 0 | 0 | 0 |
| Different company excluded (of 172) | 0 | 110 | 132 | 130 | 137 |
| Resolved (share not left possible) | 0.0 | 0.524 | 0.606 | 0.565 | 0.663 |
| Precision of matches | None | 0.667 | None | None | None |
| Precision of exclusions | None | 0.894 | 0.886 | 0.935 | 0.84 |
| AUC of P(same) | 0.5 | 0.772 | 0.838 | 0.838 | 0.806 |
| Brier score of P(same) (lower is better) | 0.25 | 0.174 | 0.2 | 0.2 | 0.189 |
| Answers rejected by validation | 0 | 1 | 0 | 0 | 0 |
| Answers missing (call failed) | 0 | 0 | 0 | 0 | 0 |
| Median seconds per packet | None | 0.84 | 0.23 | 0.23 | 0.23 |
| p90 seconds per packet | None | 1.15 | 0.28 | 0.28 | 0.28 |

Tokens: LLM 194,014 (in + out); Jev 307,191 input (≈ $0.0129 at list price; output is free).

Thresholds are the app's (`adjudicate.ai_bucket`): same ≥ 0.85 → matched, different ≥ 0.80 → excluded. "Jev choice, tuned" uses the choice's P(same) instead: excluded at ≤ 0.2 in the sub's state and ≤ 0.06 in another, matched at ≥ 0.85.

## What the rules do with each pair type

Only the uncertain ones reach the adjudicator.

| Pairs | matched | uncertain | excluded | not found | matched by rule |
|---|---|---|---|---|---|
| Same company, same name | 296 | 69 | 2 | 0 | M1 176, M3 120 |
| Same company, other name | 9 | 5 | 4 | 15 | M1b 6, M2 1, M3 2 |
| Different company, same name, same state | 10 | 3 | 0 | 0 | M1 10 |
| Different company, same name core, same state | 15 | 59 | 111 | 0 | M1b 11, M2 4 |
| Different company, same name core, other state | 60 | 110 | 1159 | 4 | M3 60 |

## By label and place

Outcomes as matched · possible · excluded. The other-state different companies are two local firms (each tax ID files in one state), so a national firm's own namesakes aren't among them.

| Pairs | n | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev choice, tuned | Jev yes/no |
|---|---|---|---|---|---|
| Same company, same state | 16 | 4 · 11 · 1 | 0 · 16 · 0 | 0 · 16 · 0 | 0 · 16 · 0 |
| Same company, other state | 58 | 0 · 46 · 12 | 0 · 41 · 17 | 0 · 49 · 9 | 0 · 32 · 26 |
| Different company, same state | 62 | 2 · 39 · 21 | 0 · 27 · 35 | 0 · 20 · 42 | 0 · 27 · 35 |
| Different company, other state | 110 | 0 · 21 · 89 | 0 · 13 · 97 | 0 · 22 · 88 | 0 · 8 · 102 |

## Matching at other thresholds

Matched if P(same) ≥ t: same-company records matched / different-company records matched.

| t | LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash) | Jev choice | Jev yes/no |
|---|---|---|---|
| 0.95 | 0/74 · 0 | 0/74 · 0 | 0/74 · 0 |
| 0.9 | 1/74 · 1 | 0/74 · 0 | 0/74 · 0 |
| 0.85 | 4/74 · 2 | 0/74 · 0 | 0/74 · 0 |
| 0.8 | 4/74 · 3 | 0/74 · 0 | 0/74 · 0 |
| 0.7 | 9/74 · 4 | 1/74 · 1 | 0/74 · 0 |
| 0.6 | 10/74 · 4 | 3/74 · 1 | 1/74 · 1 |

## LLM (openai_compat:deepseek-ai/DeepSeek-V4.1-Flash): disagreements with the silver label (15, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | TURNER CONSTRUCTION (SAN DIEGO, CA) | TURNER CONSTRUCTION (CHICAGO, IL) | different 0.85: The sub and its matched record are in San Diego, CA (E1, E2), while the candidate is in Chicago, IL with no shared address (E3), so a common name alone is not enough to join them. |
| same | NPL CONSTRUCTION (CORTLAND, IL) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.80: The matched record places the sub in Cortland, IL (E1, E2), while the candidates are at Cameron St addresses in Las Vegas, NV (E3, E4) — different states with no shared address. Same trade code and identical name are outweighed by the geographic mismatch on a common name. |
| same | NPL CONSTRUCTION (WOODBRIDGE, CT) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.85: The sub is in Woodbridge CT with a matched record at a Bradley Ave address, while both candidates are in Las Vegas NV at Cameron St addresses, with no shared address or state. Same trade code and identical name are weak given the cross-country locations. |
| same | NVR (RICHMOND, VA) | NVR (BRECKSVILLE, OH) | different 0.85: The sub NVR INC is in Richmond VA, and its matched records share the 7501 Boulders View Dr, Richmond VA address (E2-E3); the candidates are all 'NVR' in various Ohio cities and share no address or region with the sub. |
| same | TURNER CONSTRUCTION (SAN DIEGO, CA) | TURNER CONSTRUCTION (SHELTON, CT) | different 0.85: The sub is tied to San Diego, CA (E1, E2), while the candidate is a same-named Turner Construction in Shelton, CT with no shared address or region (E3). A common name in a different state with no address overlap is usually a different company. |
| same | PERFORMANCE CONTRACTING (LAKE ZURICH, IL) | PERFORMANCE CONTRACTING (LAKELAND, FL) | different 0.85: The sub is in Lake Zurich, IL (E1, E2), while the candidate is at a Lakeland, FL address with a different trade code (2383 vs 2381) and a single one-day inspection (E3); same trade code 2381 and IL location confirm the already-matched record as the real sub. |
| same | PERFORMANCE CONTRACTING (MEMPHIS, TN) | PERFORMANCE CONTRACTING (WYOMING, OH) | different 0.80: The matched record E2 places the sub in Memphis TN, while all candidates E3-E5 are in Ohio (Wyoming/Cincinnati) with no shared address; E5/E3 even share an Ohio address, indicating a separate Ohio company of the same common name. |
| same | MAXIM CRANE WORKS (STOCKTON, CA) | MAXIM CRANE WORKS (BRIDGEVILLE, PA) | different 0.85: The sub and its matched record E2 are in Stockton, CA, while all four candidates E3-E6 are in Pennsylvania (Bridgeville, Canonsburg, Bensalem) with no shared address. Same name and trade code are insufficient to bridge the cross-country gap. |
| same | TURNER CONSTRUCTION (WEST DES MOINES, IA) | TURNER CONSTRUCTION (SOMERSET, NJ) | different 0.85: The matched record E2 places the sub in West Des Moines, IA, while all candidates (E3–E6) are in New Jersey at unrelated addresses with no shared location, and 'TURNER CONSTRUCTION' is a common national name. |
| same | NPL CONSTRUCTION (EASTVALE, CA) | NPL CONSTRUCTION (HOUSTON, PA) | different 0.85: The sub's matched records (E2, E3) are located in EASTVALE, CA, while the candidates (E4, E5) are in HOUSTON, PA, with no shared address or region, and the common initials-only name is easily confused. |
| same | PAR ELECTRICAL CONTRACTORS (LENEXA, KS) | PAR ELECTRICAL CONTRACTORS (SOUTH WINDSOR, CT) | different 0.85: The sub and matched record are in LENEXA KS (E1, E2), while the candidate is in SOUTH WINDSOR CT with no shared address and a different active period (E3). Same generic name and trade code 2382 are weak when the company is in a different state. |
| same | NVR (CHARLOTTE, NC) | NVR (RICHMOND, VA) | different 0.80: The sub and its matched records are all in CHARLOTTE NC (E2), while every candidate 'NVR' record is in Virginia (RICHMOND, RESTON, WILLIAMSBURG, FAIRFAX, CHESAPEAKE) with no shared address; 'NVR' is an initials-only name prone to confusion (E7). |
| same | HOME ROOFING SOLUTIONS (ETNA, ME) | VERTEX SERVICE PARTNERS (ETNA, ME) | different 0.90: E4 is named 'VERTEX SERVICE PARTNERS', a completely different name from the sub 'HOME ROOFING SOLUTIONS, LLC'. The only overlap is the shared address 161 STAGE RD in Etna, ME, which suggests a different company occupying the same premises. |
| different | BARTON MALOW (SOUTHFIELD, MI) | BARTON MALOW BUILDERS (SOUTHFIELD, MI) | same 0.85: Candidates 'BARTON MALOW BUILDERS' share the exact addresses 26500 AMERICAN DR, SOUTHFIELD MI (E7/E2) and 1274 LIBRARY ST, DETROIT MI (E8/E6) with already-matched 'BARTON MALOW' records, same trade code 2362, so the BUILDERS variant is the same company. |
| different | STELLAR CONTRACTING (JACKSONVILLE, FL) | STELLAR GROUP (JACKSONVILLE, FL) | same 0.90: Candidate 'STELLAR GROUP' shares the exact address 2900 Hartley/Hartly Rd, Jacksonville FL 32257 and trade code 2362 with the already-matched Stellar records, all linked to the GC's sub in Jacksonville; name variant is consistent with the OSHA records already treated as the same company. |

## Jev choice: disagreements with the silver label (17, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | NVR (CHESAPEAKE, VA) | NVR (WEST CHESTER, PA) | different 0.80 (P(same) 0.12) |
| same | NPL CONSTRUCTION (HOUSTON, PA) | NPL CONSTRUCTION (GLENDALE, AZ) | different 0.91 (P(same) 0.05) |
| same | NPL CONSTRUCTION (TOPEKA, KS) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.95 (P(same) 0.03) |
| same | NPL CONSTRUCTION (CORTLAND, IL) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.93 (P(same) 0.04) |
| same | NPL CONSTRUCTION (WOODBRIDGE, CT) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.90 (P(same) 0.06) |
| same | NVR (HUNTERSVILLE, NC) | NVR (FREDERICK, MD) | different 0.92 (P(same) 0.06) |
| same | NVR (RICHMOND, VA) | NVR (BRECKSVILLE, OH) | different 0.88 (P(same) 0.07) |
| same | NVR (HUNTERSVILLE, NC) | NVR (BALTIMORE, MD) | different 0.88 (P(same) 0.09) |
| same | SUNRUN (MARLBOROUGH, MA) | SUNRUN INSTALLATION (GRAND PRAIRIE, TX) | different 0.90 (P(same) 0.08) |
| same | NVR (CHARLOTTE, NC) | NVR (LANHAM, MD) | different 0.88 (P(same) 0.09) |
| same | PETRA (GREENWOOD VILLAGE, CO) | PETRA (REDMOND, WA) | different 0.83 (P(same) 0.09) |
| same | NVR (HUNTERSVILLE, NC) | NVR (OWINGS MILLS, MD) | different 0.93 (P(same) 0.04) |
| same | NPL CONSTRUCTION (EASTVALE, CA) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.90 (P(same) 0.06) |
| same | NVR (CHARLOTTE, NC) | NVR (OWINGS MILLS, MD) | different 0.80 (P(same) 0.15) |
| same | PAR ELECTRICAL CONTRACTORS (LENEXA, KS) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | different 0.91 (P(same) 0.05) |

## Jev choice, tuned: disagreements with the silver label (9, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | NPL CONSTRUCTION (HOUSTON, PA) | NPL CONSTRUCTION (GLENDALE, AZ) | P(same) 0.05, excluded at ≤ 0.06 |
| same | NPL CONSTRUCTION (TOPEKA, KS) | NPL CONSTRUCTION (LAS VEGAS, NV) | P(same) 0.03, excluded at ≤ 0.06 |
| same | NPL CONSTRUCTION (CORTLAND, IL) | NPL CONSTRUCTION (LAS VEGAS, NV) | P(same) 0.04, excluded at ≤ 0.06 |
| same | NPL CONSTRUCTION (WOODBRIDGE, CT) | NPL CONSTRUCTION (LAS VEGAS, NV) | P(same) 0.06, excluded at ≤ 0.06 |
| same | NVR (HUNTERSVILLE, NC) | NVR (FREDERICK, MD) | P(same) 0.06, excluded at ≤ 0.06 |
| same | NVR (HUNTERSVILLE, NC) | NVR (OWINGS MILLS, MD) | P(same) 0.04, excluded at ≤ 0.06 |
| same | NPL CONSTRUCTION (EASTVALE, CA) | NPL CONSTRUCTION (LAS VEGAS, NV) | P(same) 0.06, excluded at ≤ 0.06 |
| same | PAR ELECTRICAL CONTRACTORS (LENEXA, KS) | PAR ELECTRICAL CONTRACTORS (VACAVILLE, CA) | P(same) 0.05, excluded at ≤ 0.06 |
| same | NPL CONSTRUCTION (EASTVALE, CA) | NPL CONSTRUCTION (HOUSTON, PA) | P(same) 0.02, excluded at ≤ 0.06 |

## Jev yes/no: disagreements with the silver label (26, first 15)

| Label | Search (A) | Candidate (B) | Answer |
|---|---|---|---|
| same | NVR (CHESAPEAKE, VA) | NVR (WEST CHESTER, PA) | different 0.81 (P(same) 0.19) |
| same | PERFORMANCE CONTRACTING (CALVERT CITY, KY) | PERFORMANCE CONTRACTING (NORTH HIGHLANDS, CA) | different 0.84 (P(same) 0.16) |
| same | PERFORMANCE CONTRACTING (MEMPHIS, TN) | PERFORMANCE CONTRACTING (LAKELAND, FL) | different 0.80 (P(same) 0.20) |
| same | NPL CONSTRUCTION (HOUSTON, PA) | NPL CONSTRUCTION (GLENDALE, AZ) | different 0.85 (P(same) 0.15) |
| same | NPL CONSTRUCTION (TOPEKA, KS) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.90 (P(same) 0.10) |
| same | NPL CONSTRUCTION (CORTLAND, IL) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.87 (P(same) 0.13) |
| same | NPL CONSTRUCTION (WOODBRIDGE, CT) | NPL CONSTRUCTION (LAS VEGAS, NV) | different 0.85 (P(same) 0.15) |
| same | NVR (HUNTERSVILLE, NC) | NVR (FREDERICK, MD) | different 0.83 (P(same) 0.17) |
| same | NVR (RICHMOND, VA) | NVR (BRECKSVILLE, OH) | different 0.83 (P(same) 0.17) |
| same | ARCHER EXTERIORS (MANASSAS, VA) | ARCHER EXTERIORS (PITTSGROVE, NJ) | different 0.80 (P(same) 0.20) |
| same | NVR (HUNTERSVILLE, NC) | NVR (BALTIMORE, MD) | different 0.82 (P(same) 0.18) |
| same | NVR (CHARLOTTE, NC) | NVR (LANHAM, MD) | different 0.82 (P(same) 0.18) |
| same | ARCHITECTURAL GLASS METAL (NASHVILLE, TN) | ARCHITECTURAL GLASS METAL (INDIANAPOLIS, IN) | different 0.80 (P(same) 0.20) |
| same | PERFORMANCE CONTRACTING (WOODINVILLE, WA) | PERFORMANCE CONTRACTING (WYOMING, OH) | different 0.83 (P(same) 0.17) |
| same | PERFORMANCE CONTRACTING (CALVERT CITY, KY) | PERFORMANCE CONTRACTING (GRANDVIEW, MO) | different 0.82 (P(same) 0.18) |

Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, so some "disagreements" are label errors. Read them before trusting a small difference.
