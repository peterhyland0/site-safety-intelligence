# Matching rules, one at a time (silver labels from ITA EINs)

3264 searches (general 1500, person 282, shared address 274, joint venture 93, branch or sibling 274, related facility 268, common name 273, licence 300) on warehouse 20261004T230852Z: 140,766 records decided, 23,612 of them labelled; 8,020 graded after the cap of 3 per search, rule and bucket. 477 s.

The targeted pools oversample the cases their rules act on, so each share describes a rule where it acts, not a GC's usual mix. Intervals are 95% (Wilson) and treat records as independent, which they aren't when a few firms supply most of a rule's records (firms: distinct tax IDs searched). A rule with under ~30 labelled records, or a handful of firms, settles little. Silver labels count a corporate family's divisions as different companies.

## Rules that match

Share same = precision: the rest are records of another company counted in the sub's scorecard.

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| M1 | Same name, same state (distinctive, or the same city) | 967 | 1620 | 950 (585) | 946 | 4 (3) | 0.996 [0.99–1.0] | 0 of 4 reviewed |
| M1b | Same distinctive core, differing only by descriptor words | 113 | 180 | 44 (21) | 20 | 24 (9) | 0.455 [0.32–0.6] | 0 of 24 reviewed |
| M1s | The sub's name plus OF <PLACE>, in its city, at an address where another OF <PLACE> of it files | 1 | 2 | 0 (0) | 0 | 0 (0) |  |  |
| M2 | At a matched address, the name differs only by spelling | 237 | 318 | 40 (28) | 28 | 12 (6) | 0.7 [0.55–0.82] | 0 of 12 reviewed |
| M3 | Same distinctive name in another state | 409 | 3593 | 469 (120) | 366 | 103 (40) | 0.78 [0.74–0.82] | 0 of 103 reviewed |
| L1 | Linked to the licence number entered | 91 | 124 | 112 (78) | 112 | 0 (0) | 1.0 [0.97–1.0] |  |

## Rules that exclude

Share same = the share wrongly excluded: the sub's own records hidden.

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| X1 | A different real word in the name | 2317 | 86030 | 3497 (1336) | 18 | 3479 (2937) | 0.005 [0.0–0.01] | 0 of 18 reviewed |
| X3 | A common name with different words | 706 | 21243 | 1204 (472) | 1 | 1203 (1076) | 0.001 [0.0–0.0] | 0 of 1 reviewed |
| X5 | A person's name in another city or state | 17 | 23 | 0 (0) | 0 | 0 (0) |  |  |

## Rules that hold records back

Share same = how often the held-back record was the sub's (near 1 the rule could match, near 0 it could exclude).

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| M3u | M3 held back: a '<word> CONSTRUCTION / ELECTRIC' name under a trade code the sub's records lack | 61 | 109 | 23 (15) | 13 | 10 (10) | 0.565 [0.37–0.74] |  |
| S1 | Differs only by OF <STATE> / AT <project> | 416 | 20537 | 482 (208) | 5 | 477 (458) | 0.01 [0.0–0.02] |  |
| S2 | The sub's name plus BRANCH / DIVISION / OFFICE | 9 | 51 | 2 (1) | 2 | 0 (0) | 1.0 [0.34–1.0] |  |
| S3 | The sub's name plus a real word, at an address the sub uses | 120 | 209 | 48 (28) | 18 | 30 (21) | 0.375 [0.25–0.52] |  |
| S4 | The sub's name plus a state, or the record's own city | 42 | 110 | 23 (8) | 3 | 20 (8) | 0.13 [0.05–0.32] |  |
| P1 | A person's name without a city to tell people apart | 9 | 9 | 2 (2) | 2 | 0 (0) | 1.0 [0.34–1.0] |  |
| P3 | A company named after a person, in another city or state | 53 | 90 | 23 (13) | 23 | 0 (0) | 1.0 [0.86–1.0] |  |
| J1 | A joint venture at a member's address | 62 | 85 | 0 (0) | 0 | 0 (0) |  |  |
| U3 | Same family name, a different trade word | 383 | 1088 | 149 (92) | 20 | 129 (98) | 0.134 [0.09–0.2] |  |
| U2 | A common name with other words, same city | 125 | 183 | 42 (29) | 7 | 35 (34) | 0.167 [0.08–0.31] |  |
| U4 | The sub's common name in another state | 121 | 378 | 72 (36) | 18 | 54 (52) | 0.25 [0.16–0.36] |  |
| G1 | Initials-only names | 104 | 431 | 61 (31) | 31 | 30 (29) | 0.508 [0.39–0.63] |  |
| N1 | A related facility (not coded construction), by name | 290 | 809 | 319 (117) | 272 | 47 (21) | 0.853 [0.81–0.89] |  |
| R1 | A red-flagged record at an address the company uses | 115 | 127 | 54 (29) | 6 | 48 (18) | 0.111 [0.05–0.22] |  |
| U | Anything else the rules can't settle | 671 | 3417 | 404 (195) | 127 | 277 (214) | 0.314 [0.27–0.36] |  |

## Rules that never fired in these searches

X2 (A different generic name), P2 (Another person's name at a matched address).

## Apparent errors (first 8 per rule)

A matched record labelled different, or an excluded one labelled same. Many are a family's divisions filing under their own EINs; review.jsonl holds them for a verdict.

### M1 (matched): 4

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| different (local firms) | PIPE JACKING TRENCHLESS, INC. (SAN DIEGO, CA) | PIPE JACKING TRENCHLESS, INC. (2130 LA MIRADA DR, VISTA, CA) |  |
| different | PEGASUS LINK CONSTRUCTORS (DALLAS, TX) | PEGASUS LINK CONSTRUCTORS (12170 ABRAMS RD, DALLAS, TX) |  |
| different (local firms) | PIPE JACKING TRENCHLESS, INC. (VISTA, CA) | PIPE JACKING TRENCHLESS, INC. (16885 W BERNARDO DR STE 300, SAN DIEGO, CA) |  |
| different (local firms) | BANKER INSULATION, INC. (TUCSON, AZ) | BANKER INSULATION, INC. (111 S 56TH ST, CHANDLER, AZ) |  |

### M1b (matched): 24

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| different (local firms) | 158992 - ARISTEO CONSTRUCTION COMPANY (LIVONIA, MI) | ARISTEO (12811 FARMINGTON RD, LIVONIA, MI) |  |
| different | HENSEL PHELPS (HONOLULU, HI) | HENSEL AND PHELPS CONSTRUCTION CO. (PO BOX 6452, KANEOHE, HI) |  |
| different (local firms) | JAKE MARSHALL SERVICE, INC. (CHATTANOOGA, TN) | JAKE MARSHALL, LLC (2912 S HICKORY ST, CHATTANOOGA, TN) |  |
| different | HENSEL PHELPS CONSTRUCTION CO (HONOLULU, HI) | HENSEL PHELPS (841 BISHOP ST STE 2001, HONOLULU, HI) |  |
| different | BRANDSAFWAY INDUSTRIES (MC KEES ROCKS, PA) | BRANDSAFWAY SERVICES LLC (BRANDSAFWAY AIRPORT BUSINESS COMPLEX 10 INDUSTRIAL HWY, LESTER, PA) |  |
| different (local firms) | HAGERMAN INC. (FORT WAYNE, IN) | 109938 - HAGERMAN CONSTRUCTION COMPANY (510 W WASHINGTON BLVD, FORT WAYNE, IN) |  |
| different | BRANDSAFWAY INDUSTRIES (MC KEES ROCKS, PA) | BRANDSAFWAY SERVICES LLC (10 INDUSTRIAL HWY BUILDING E MS 24 STE 201, LESTER, PA) |  |
| different | THE CHRISTMAN COMPANY (LANSING, MI) | CHRISTMAN CONSTRUCTORS, INC. (324 E S ST, LANSING, MI) |  |

### M2 (matched): 12

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| different | BRANDSAFWAY LLC (BEAUMONT, TX) | BRANDSAFWAY SERVICES LLC (90422 HWY 99, EUGENE, OR) |  |
| different | 149146 - BRANDSAFWAY SOLUTIONS, LLC (RALEIGH, NC) | BRANDSAFWAY SERVICES LLC (90422 HWY 99, EUGENE, OR) |  |
| different | HENKELS & MCCOY, INC. (AURORA, IL) | HENKEL'S & MCCOY WEST, LLC (2840 FICUS ST, POMONA, CA) |  |
| different (local firms) | DEL-AIR HEATING, AIR CONDITIONING & REFRIGERATION, INC. (SANFORD, FL) | DEL-AIR HEATING & AIR CONDITIONING (531 CODISCO WAY, SANFORD, FL) |  |
| different | BRANDSAFWAY INDUSTRIES, LLC (LESTER, PA) | BRANDSAFWAY SERVICES LLC (90422 HWY 99, EUGENE, OR) |  |
| different (local firms) | CORESLAB STRUCTURES (INDIANAPOLIS, IN) | 135390 - CORESLAB STRUCTURES (ATLANTA) INC. (1655 NOAHS ARK RD, LAKE SPIVEY, GA) |  |
| different (local firms) | WA317965131 - SYNERGY INC (WOODINVILLE, WA) | WA317942742 - SYNERGY CONSTRUCTION INC (14040 NE 181ST ST, WOODINVILLE, WA) |  |
| different (local firms) | 104048 - NOR-SON CONSTRUCTION LLC (BAXTER, MN) | 103175 - NOR-SON INC (7900 HASTINGS RD, BAXTER, MN) |  |

### M3 (matched): 103

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| different | HENSEL PHELPS (HONOLULU, HI) | HENSEL PHELPS CONSTRUCTION CO. (420 SIXTH AVE, GREELEY, CO) |  |
| different | BRANDSAFWAY INDUSTRIES, LLC (LESTER, PA) | BRANDSAFWAY SOLUTIONS, LLC (11208 BOGGY CREEK RD, ORLANDO, FL) |  |
| different (local firms) | D.R. HORTON, INC. (MOUNT LAUREL, NJ) | D.R. HORTON (5724 N W 132ND, OKLAHOMA CITY, OK) |  |
| different | 133410 - D. R. HORTON, INC (MORRISVILLE, NC) | D.R. HORTON, INC. (4400 ALAMEDA BLVD NE STE B, ALBUQUERQUE, NM) |  |
| different | BRANDSAFWAY SERVICES LLC (BENICIA, CA) | BRANDSAFWAY INDUSTRIES (501 ROBB ST, MC KEES ROCKS, PA) |  |
| different | 149146 - BRANDSAFWAY SOLUTIONS, LLC (RALEIGH, NC) | BRANDSAFWAY SERVICES, LLC (5251 W 130TH ST, CLEVELAND, OH) |  |
| different | 67978 - BRANDSAFWAY INDUSTRIES LLC (INDIANAPOLIS, IN) | BRANDSAFWAY LLC (3674 HWY 51, LA PLACE, LA) |  |
| different | D.R. HORTON, INC. (MOUNT LAUREL, NJ) | 139010 - D.R. HORTON, INC. (408 MENDENHALL OAKS STE 101, HIGH POINT, NC) |  |

### X1 (excluded): 18

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| same | TK ELEVATOR RICHMOND (ASHLAND, VA) | TK ELEVATOR CORPORATION (250 KING MANOR DR, KING OF PRUSSIA, PA) |  |
| same | SIEMENS BUILDING TECHNOLOGIES INC. (ANCHORAGE, AK) | SIEMENS INDUSTRY, INC. (7000 SIEMENS DR, WENDELL, NC) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | TINDALL CORPORATION (PO BOX 280, CONLEY, GA) |  |
| same | LGI HOMES (THE WOODLANDS, TX) | LGI HOMES CORPORATE, LLC (1450 LAKE ROBBINS DR STE 430 ATTN JAMIE SCHILLING, THE WOODLANDS, TX) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | 75691 - TINDALL CORPORATION (2273 HAYNE ST, SPARTANBURG, SC) |  |
| same | TK ELEVATOR RICHMOND (ASHLAND, VA) | TK ELEVATOR CORPORATION (788 CIR 75 PKWY SE, ATLANTA, GA) |  |
| same | TK ELEVATOR RICHMOND (ASHLAND, VA) | TK ELEVATOR (929 EASTWIND DR STE 218, WESTERVILLE, OH) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | TINDALL CORPORATION (3361 GRANT RD, CONLEY, GA) |  |

### X3 (excluded): 1

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| same | PCL CONSTRUCTION SERVICES, INC. (ORLANDO, FL) | PCL CONSTRUCTION, INC. (2000 S COLORADO BLVD TOWER 2 STE 2 500, DENVER, CO) |  |

