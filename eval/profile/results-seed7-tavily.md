# Company profiles on the adjudication eval (seed 7)

43 distinct searches; 43 profiles built (0 failed, retried on the next run), 40 found the company. 61 uncertain cases from those searches (24 same company, 37 different); 57 have a profile, 22 have B at a listed location (4 at an address).

Profiles by tavily-v2+deepseek-ai/DeepSeek-V4.1-Flash: 158,791 input and 21,805 output tokens, 43 searches, ≈ $0.42 (≈ $0.01 a profile); median 3 s, slowest 8 s.

Counts of B records. 'asked' means the GC is asked (the question approach); nothing else waits for the GC.

## All cases (61)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 4 | 0 | 2 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 1 |
| same asked (unsure) | 0 | 0 | 0 | 0 | 5 |
| same excluded (wrong) | 5 | 0 | 0 | 1 | 0 |
| different matched (wrong merge) | 1 | 5 | 0 | 1 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 3 |
| different asked (unsure) | 0 | 0 | 0 | 0 | 13 |
| different excluded | 20 | 19 | 27 | 25 | 17 |
| rejected | 3 | 0 | 0 | 0 | 0 |

## Cases with a profile (57)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 4 | 0 | 2 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 1 |
| same asked (unsure) | 0 | 0 | 0 | 0 | 5 |
| same excluded (wrong) | 5 | 0 | 0 | 1 | 0 |
| different matched (wrong merge) | 1 | 5 | 0 | 1 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 3 |
| different asked (unsure) | 0 | 0 | 0 | 0 | 13 |
| different excluded | 17 | 16 | 24 | 22 | 14 |
| rejected | 3 | 0 | 0 | 0 | 0 |

## Where the profile changed an adjudicator's answer (23)

| Label | Search (A) | Candidate (B) | Listed | DeepSeek today → with profile | Jev today → with profile |
|---|---|---|---|---|---|
| same | TURNER CONSTRUCTION (NEW YORK, NY) | TURNER CONSTRUCTION (ALBANY, NY) | - | possible → matched | possible → possible |
| same | NPL CONSTRUCTION (TULSA, OK) | NPL CONSTRUCTION (LAS VEGAS, NV) | - | excluded → possible | possible → excluded |
| same | MCCARTHY BUILDING COMPANIES (ROSEVILLE, CA) | MCCARTHY BUILDING COMPANIES (NEWPORT BEACH, CA) | city | possible → matched | possible → matched |
| same | HELIX ELECTRIC (OAKLAND, CA) | HELIX ELECTRIC (MANASSAS, VA) | address | excluded → matched | possible → possible |
| same | PERFORMANCE CONTRACTING (PORTLAND, OR) | PERFORMANCE CONTRACTING (CARMEL, IN) | - | excluded → possible | possible → possible |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | city | excluded → possible | possible → possible |
| same | AWT ENVIRONMENTAL SERVICES (SAYREVILLE, NJ) | AWT ENVIRONMENTAL SERVICES (OLD BRIDGE, NJ) | city | possible → matched | possible → matched |
| same | SAK CONSTRUCTION (ROCKLIN, CA) | SAK CONSTRUCTION (O FALLON, MO) | city | excluded → possible | possible → possible |
| different | FOCUS PLUMBING (LAS VEGAS, NV) | FOCUS CONCRETE (LAS VEGAS, NV) | address | excluded → possible | excluded → excluded |
| different | DESERT PLASTERING (NORTH LAS VEGAS, NV) | DESERT FRAMING (NORTH LAS VEGAS, NV) | city | possible → excluded | excluded → excluded |
| different | FOCUS PLUMBING (LAS VEGAS, NV) | FOCUS FIRE PROTECTION (LAS VEGAS, NV) | address | possible → possible | excluded → possible |
| different | AAT ROOFING (PORT ORANGE, FL) | AAT RESTORATION GROUP (PORT ORANGE, FL) | city | possible → possible | possible → excluded |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | possible → matched | possible → possible |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | possible → matched | possible → possible |
| different | DESERT PLASTERING (NORTH LAS VEGAS, NV) | DESERT FRAMING (NORTH LAS VEGAS, NV) | city | possible → excluded | excluded → excluded |
| different | MEADE (WILLOWBROOK, IL) | MEADE ELECTRIC (WILLOWBROOK, IL) | address | possible → possible | excluded → possible |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | possible → matched | possible → possible |
| different | EASTWOOD CONTRACTORS (BREWER, ME) | EASTWOOD HOMES (CHARLOTTE, NC) | - | excluded → possible | possible → excluded |
| different | PROGRESSIVE ELECTRIC (LIVONIA, MI) | PROGRESSIVE ELECTRIC (CHARLESTON, WV) | - | excluded → possible | possible → possible |
| different | PROGRESSIVE ELECTRIC (LIVONIA, MI) | PROGRESSIVE ELECTRIC (CHARLESTON, WV) | - | excluded → possible | possible → possible |
| different | WRIGHT CONSTRUCTION (MOUNT HOLLY, VT) | WRIGHT CONSTRUCTION (COLLIERVILLE, TN) | - | excluded → excluded | excluded → possible |
| different | UNITY ELECTRIC (EAST RUTHERFORD, NJ) | UNITY ELECTRIC (SHORELINE, WA) | - | possible → excluded | possible → possible |
| different | BIG D CONSTRUCTION (PLEASANTON, CA) | BIG D CONSTRUCTION (SALT LAKE CITY, UT) | city | possible → matched | excluded → matched |
