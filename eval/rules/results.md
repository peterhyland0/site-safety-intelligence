# Matching rules, one at a time (silver labels from ITA EINs)

2986 searches (general 1500, person 282, shared address 271, joint venture 93, branch or sibling 272, related facility 268, licence 300) on warehouse 20261004T171230Z: 140,473 records decided, 23,424 of them labelled; 7,842 graded after the cap of 3 per search, rule and bucket. 353 s.

The targeted pools oversample the cases their rules act on, so each share describes a rule where it acts, not a GC's usual mix. Intervals are 95% (Wilson) and treat records as independent, which they aren't when a few firms supply most of a rule's records (firms: distinct tax IDs searched). A rule with under ~30 labelled records, or a handful of firms, settles little. Silver labels count a corporate family's divisions as different companies.

## Rules that match

Share same = precision: the rest are records of another company counted in the sub's scorecard.

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| M1 | Same name, same state (distinctive, or the same city) | 899 | 1544 | 879 (547) | 875 | 4 (3) | 0.995 [0.99–1.0] | 0 of 4 reviewed |
| M1b | Same distinctive core, differing only by descriptor words | 111 | 177 | 43 (21) | 19 | 24 (9) | 0.442 [0.3–0.59] | 0 of 24 reviewed |
| M2 | At a matched address, the name differs only by spelling | 225 | 306 | 36 (26) | 24 | 12 (6) | 0.667 [0.5–0.8] | 0 of 12 reviewed |
| M3 | Same distinctive name in another state | 403 | 3577 | 461 (120) | 359 | 102 (40) | 0.779 [0.74–0.81] | 0 of 102 reviewed |
| L1 | Linked to the licence number entered | 93 | 126 | 114 (80) | 114 | 0 (0) | 1.0 [0.97–1.0] |  |

## Rules that exclude

Share same = the share wrongly excluded: the sub's own records hidden.

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| X1 | A different real word in the name | 2320 | 86165 | 3510 (1339) | 20 | 3490 (2939) | 0.006 [0.0–0.01] | 0 of 20 reviewed |
| X3 | A common name with different words | 709 | 21478 | 1216 (476) | 1 | 1215 (1088) | 0.001 [0.0–0.0] | 0 of 1 reviewed |
| X4 | A common name in another state | 22 | 94 | 17 (7) | 10 | 7 (7) | 0.588 [0.36–0.78] | 0 of 10 reviewed |
| X5 | A person's name in another city or state | 17 | 23 | 0 (0) | 0 | 0 (0) |  |  |

## Rules that hold records back

Share same = how often the held-back record was the sub's (near 1 the rule could match, near 0 it could exclude).

| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |
|---|---|---|---|---|---|---|---|---|
| M3u | M3 held back: a '<word> CONSTRUCTION / ELECTRIC' name under a trade code the sub's records lack | 62 | 110 | 24 (15) | 14 | 10 (10) | 0.583 [0.39–0.76] |  |
| S1 | Differs only by OF <STATE> / AT <project> | 415 | 20424 | 479 (209) | 5 | 474 (455) | 0.01 [0.0–0.02] |  |
| S2 | The sub's name plus BRANCH / DIVISION / OFFICE | 9 | 51 | 2 (1) | 2 | 0 (0) | 1.0 [0.34–1.0] |  |
| S3 | The sub's name plus a real word, at an address the sub uses | 120 | 238 | 50 (30) | 19 | 31 (20) | 0.38 [0.26–0.52] |  |
| P1 | A person's name without a city to tell people apart | 9 | 9 | 2 (2) | 2 | 0 (0) | 1.0 [0.34–1.0] |  |
| P3 | A company named after a person, in another city or state | 54 | 91 | 24 (13) | 24 | 0 (0) | 1.0 [0.86–1.0] |  |
| J1 | A joint venture at a member's address | 62 | 85 | 0 (0) | 0 | 0 (0) |  |  |
| U3 | Same family name, a different trade word | 384 | 1087 | 149 (92) | 20 | 129 (100) | 0.134 [0.09–0.2] |  |
| U2 | A common name with other words, same city | 103 | 151 | 29 (21) | 5 | 24 (23) | 0.172 [0.08–0.35] |  |
| G1 | Initials-only names | 104 | 431 | 61 (31) | 31 | 30 (29) | 0.508 [0.39–0.63] |  |
| N1 | A related facility (not coded construction), by name | 289 | 800 | 315 (118) | 268 | 47 (21) | 0.851 [0.81–0.89] |  |
| R1 | A red-flagged record at an address the company uses | 111 | 123 | 51 (29) | 3 | 48 (18) | 0.059 [0.02–0.16] |  |
| U | Anything else the rules can't settle | 637 | 3383 | 380 (183) | 104 | 276 (213) | 0.274 [0.23–0.32] |  |

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

### M3 (matched): 102

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

### X1 (excluded): 20

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| same | TK ELEVATOR RICHMOND (ASHLAND, VA) | TK ELEVATOR CORPORATION (250 KING MANOR DR, KING OF PRUSSIA, PA) |  |
| same | SIEMENS BUILDING TECHNOLOGIES INC. (ANCHORAGE, AK) | SIEMENS INDUSTRY, INC. (7000 SIEMENS DR, WENDELL, NC) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | TINDALL CORPORATION (PO BOX 280, CONLEY, GA) |  |
| same | LGI HOMES (THE WOODLANDS, TX) | LGI HOMES CORPORATE, LLC (1450 LAKE ROBBINS DR STE 430 ATTN JAMIE SCHILLING, THE WOODLANDS, TX) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | 75691 - TINDALL CORPORATION (2273 HAYNE ST, SPARTANBURG, SC) |  |
| same | TK ELEVATOR RICHMOND (ASHLAND, VA) | TK ELEVATOR CORPORATION (788 CIR 75 PKWY SOUTHEAST, ATLANTA, GA) |  |
| same | TINDALL CORPORATION-VIRGINIA DIVISION (PETERSBURG, VA) | TINDALL CORPORATION (3361 GRANT RD, CONLEY, GA) |  |
| same | LIMBACH FACILITY SERVICES, LLC (WILMINGTON, MA) | LIMBACH COMPANY (822 CLEVELAND AVE, COLUMBUS, OH) |  |

### X3 (excluded): 1

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| same | PCL CONSTRUCTION SERVICES, INC. (ORLANDO, FL) | PCL CONSTRUCTION, INC. (2000 S COLORADO BLVD TOWER 2 STE 2 500, DENVER, CO) |  |

### X4 (excluded): 10

| Silver | Search (A) | Record (B) | Verdict |
|---|---|---|---|
| same | PREMIER ROOFING COMPANY (OMAHA, NE) | PREMIER ROOFING COMPANY (11406 GRAVOIS RD, SAINT LOUIS, MO) |  |
| same | PREMIER ROOFING COMPANY (OMAHA, NE) | PREMIER ROOFING LLC (406 AUBURN DR, COLORADO SPRINGS, CO) |  |
| same | PREMIER ROOFING LLC (COLORADO SPRINGS, CO) | PREMIER ROOFING COMPANY (11406 GRAVOIS RD, SAINT LOUIS, MO) |  |
| same | POWER HOME SOLAR LLC (MOORESVILLE, NC) | POWER HOME SOLAR LLC (51531 GRATIOT AVE, CHESTERFIELD, MI) |  |
| same | POWER HOME SOLAR LLC (KENTWOOD, MI) | POWER HOME SOLAR LLC (270 INTERNATIONAL DR, CONCORD, NC) |  |
| same | PREMIER ROOFING COMPANY (OMAHA, NE) | PREMIER ROOFING COMPANY (3201 E MULBERRY ST UNIT B, FORT COLLINS, CO) |  |
| same | POWER HOME SOLAR LLC (KENTWOOD, MI) | POWER HOME SOLAR LLC (919 N MAIN ST, MOORESVILLE, NC) |  |
| same | POWER HOME SOLAR LLC (MOORESVILLE, NC) | POWER HOME SOLAR LLC (4652 DANVERS DR SE, KENTWOOD, MI) |  |

