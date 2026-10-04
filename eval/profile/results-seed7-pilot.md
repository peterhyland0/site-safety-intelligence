# Company profiles on the adjudication eval (seed 7, pilot)

40 distinct searches; profiles found for 25 (0 not found or failed). 33 uncertain cases from those searches (24 same company, 9 different); 23 have a profile, 8 have B at a listed location (0 at an address).

Profiles by claude-sonnet-5-5: 2,129,506 input and 33,093 output tokens, 56 searches, ≈ $5.15 (≈ $0.21 a profile); median 34 s, slowest 49 s.

Counts of B records. 'asked' means the GC is asked (the question approach); nothing else waits for the GC.

## All cases (33)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 3 | 0 | 3 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 0 |
| same excluded (wrong) | 5 | 1 | 0 | 0 | 0 |
| different matched (wrong merge) | 1 | 2 | 0 | 0 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 0 |
| different excluded | 4 | 4 | 5 | 5 | 4 |
| rejected | 2 | 1 | 0 | 0 | 0 |

## Cases with a profile (23)

| | llm today | llm context | jev today | jev context | question |
|---|---|---|---|---|---|
| same matched | 0 | 3 | 0 | 3 | 0 |
| same asked (same) | 0 | 0 | 0 | 0 | 0 |
| same excluded (wrong) | 4 | 0 | 0 | 0 | 0 |
| different matched (wrong merge) | 1 | 2 | 0 | 0 | 0 |
| different asked (same, misleading) | 0 | 0 | 0 | 0 | 0 |
| different excluded | 4 | 4 | 5 | 5 | 4 |
| rejected | 1 | 0 | 0 | 0 | 0 |

## Where the profile changed an adjudicator's answer (10)

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
