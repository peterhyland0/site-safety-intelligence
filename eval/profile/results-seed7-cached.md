# Company profiles on the adjudication eval (seed 7)

43 distinct searches; 43 profiles built (0 failed, retried on the next run), 43 found the company. 61 uncertain cases from those searches (24 same company, 37 different); 37 have a profile, 14 have B at a listed location (4 at an address).

Profiles by claude-sonnet-5-5: 3,418,552 input and 55,464 output tokens, 102 searches, ≈ $8.41 (≈ $0.20 a profile); median 32 s, slowest 52 s.

Counts of B records. 'asked' means the GC is asked (the question approach); nothing else waits for the GC.

## All cases (61)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 3 | 0 | 3 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 0 |
| same asked (unsure) | 0 | 0 | 0 | 0 | 3 |
| same excluded (wrong) | 5 | 1 | 0 | 0 | 0 |
| different matched (wrong merge) | 1 | 3 | 0 | 0 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 4 |
| different asked (unsure) | 0 | 0 | 0 | 0 | 7 |
| different excluded | 20 | 18 | 27 | 24 | 20 |
| rejected | 3 | 2 | 0 | 0 | 0 |

## Cases with a profile (37)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 3 | 0 | 3 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 0 |
| same asked (unsure) | 0 | 0 | 0 | 0 | 3 |
| same excluded (wrong) | 4 | 0 | 0 | 0 | 0 |
| different matched (wrong merge) | 1 | 3 | 0 | 0 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 4 |
| different asked (unsure) | 0 | 0 | 0 | 0 | 7 |
| different excluded | 13 | 11 | 17 | 14 | 10 |
| rejected | 2 | 1 | 0 | 0 | 0 |

## Where the profile changed an adjudicator's answer (15)

| Label | Search (A) | Candidate (B) | Listed | DeepSeek today → with profile | Jev today → with profile |
|---|---|---|---|---|---|
| same | NPL CONSTRUCTION (TULSA, OK) | NPL CONSTRUCTION (LAS VEGAS, NV) | - | excluded → possible | possible → possible |
| same | HELIX ELECTRIC (OAKLAND, CA) | HELIX ELECTRIC (MANASSAS, VA) | - | excluded → possible | possible → possible |
| same | STANDARD DRYWALL (JACKSON, WY) | STANDARD DRYWALL (DEL VALLE, TX) | city | excluded → possible | possible → possible |
| same | AWT ENVIRONMENTAL SERVICES (SAYREVILLE, NJ) | AWT ENVIRONMENTAL SERVICES (OLD BRIDGE, NJ) | city | possible → matched | possible → matched |
| same | TEAM INDUSTRIAL SERVICES (SYLVANIA, OH) | TEAM INDUSTRIAL SERVICES (PASADENA, TX) | - | possible → matched | possible → matched |
| same | SUMMIT CONTRACTING GROUP (ATLANTA, GA) | SUMMIT CONTRACTING GROUP (JACKSONVILLE, FL) | city | possible → matched | possible → matched |
| same | SAK CONSTRUCTION (ROCKLIN, CA) | SAK CONSTRUCTION (O FALLON, MO) | - | excluded → possible | possible → possible |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | possible → matched | possible → possible |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | possible → matched | possible → possible |
| different | BONE DRY COMMERCIAL ROOFING (INDIANAPOLIS, IN) | BONE DRY ROOFING (INDIANAPOLIS, IN) | city | matched → possible | possible → possible |
| different | MEADE (WILLOWBROOK, IL) | MEADE ELECTRIC (WILLOWBROOK, IL) | address | possible → possible | excluded → possible |
| different | PROGRESSIVE ELECTRIC (LIVONIA, MI) | PROGRESSIVE ELECTRIC (CHARLESTON, WV) | - | excluded → possible | possible → possible |
| different | PROGRESSIVE ELECTRIC (LIVONIA, MI) | PROGRESSIVE ELECTRIC (CHARLESTON, WV) | - | excluded → possible | possible → possible |
| different | WRIGHT CONSTRUCTION (MOUNT HOLLY, VT) | WRIGHT CONSTRUCTION (COLLIERVILLE, TN) | - | excluded → excluded | excluded → possible |
| different | BIG D CONSTRUCTION (PLEASANTON, CA) | BIG D CONSTRUCTION (SALT LAKE CITY, UT) | city | possible → matched | excluded → possible |
