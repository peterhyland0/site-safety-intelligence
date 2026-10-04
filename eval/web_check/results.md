# Web check on Clark Construction Group's records

43 records Clark's lookup returned, each checked by hand ([gold.jsonl](gold.jsonl)), against the web check ([ssi/llm/web_check.py](../../ssi/llm/web_check.py)) with Clark's profile (clarkconstruction.com). One search per record group; model web-v2+deepseek-ai/DeepSeek-V4.1-Flash.

| Records | n | right | wrong "same" | wrong "different" | unsure |
|---|---|---|---|---|---|
| all | 43 | 29 | 0 | 0 | 14 |
| Clark's own (hand) | 26 | 20 | 0 | 0 | 6 |
| likely Clark's (hand) | 3 | 0 | 0 | 0 | 3 |
| other companies (hand) | 14 | 9 | 0 | 0 | 5 |
| possible in the app | 17 | 12 | 0 | 0 | 5 |
| excluded in the app | 25 | 16 | 0 | 0 | 9 |
| kind: office | 20 | 16 | 0 | 0 | 4 |
| kind: job site | 4 | 1 | 0 | 0 | 3 |
| kind: subsidiary | 5 | 3 | 0 | 0 | 2 |
| kind: other | 14 | 9 | 0 | 0 | 5 |

"likely" records count as Clark's.

| # | OSHA name | Place | App | Hand | Check | Company found | Why |
|---|---|---|---|---|---|---|---|
| 1 | CLARK CONSTRUCTION GROUP | 7500 Old Georgetown Rd, Bethesda MD | matched | same | same | Clark Construction Group, LLC | its website is clarkconstruction.com, your sub's |
| 2 | CLARK CONCRETE CONTRACTORS | 7500 Old Georgetown Rd, Bethesda MD | possible | same | unsure | Clark Concrete LLC | only the names are alike: no page ties it to your sub's website or names your sub as its parent |
| 3 | CLARK CONCRETE CONTRACTORS | 7900 Westpark Dr, Mclean VA | possible | same | same | Clark Concrete | its website is clarkconstruction.com, your sub's |
| 4 | CLARK CONSTRUCTION | 7500 Old Georgetown Rd, Bethesda MD | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 5 | CLARK CONSTRUCTION GROUP | 800 K St NW, Washington DC | possible | same | same | Clark Construction Group, LLC | its website is clarkconstruction.com, your sub's |
| 6 | CLARK CONSTRUCTION GROUP | 216 S Jefferson St Ste 502, Chicago IL | possible | same | same | Clark Construction Group, LLC | its website is clarkconstruction.com, your sub's |
| 7 | CLARK CONSTRUCTION GROUP | 1627 Main St Ste 400, Kansas City MO | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 8 | CLARK CONSTRUCTION GROUP | 560 Mill St Ste 200, Reno NV | possible | likely | unsure | Clark Construction | only the names are alike: no page ties it to your sub's website or names your sub as its parent |
| 9 | CLARK CONSTRUCTION GROUP | 160 9th Ave N, Nashville TN | possible | likely | unsure |  | The search results mention Clark Construction Group, LLC and list Nashville, TN as one of its regional offices, but none of them links 'Clark Construction Group LLC' to the inspected address 160 9TH A |
| 10 | CLARK CONSTRUCTION GROUP | 4900 N Mesa St Ste 200, El Paso TX | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 11 | CLARK CONSTRUCTION GROUP | 711 Louisiana St Ste 2000, Houston TX | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 12 | CLARK CONSTRUCTION GROUP | 1901 S Bell St, Arlington VA | possible | same | unsure |  | None of the search results mention 'CLARK CONSTRUCTION GROUP, LLC' or the address 1901 S BELL ST, ARLINGTON, VA. The results are unrelated lists (Pennsylvania UC non-compliance, San Antonio vacant bui |
| 13 | CLARK CONSTRUCTION GROUP | 7900 West Park Dr, Mclean VA | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 14 | CLARK CONSTRUCTION GROUP | 7900 Westpark Dr, Mclean VA | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 15 | CLARK CONSTRUCTION GROUP | 3810 W Broad St Ste 103, Richmond VA | possible | same | same | Clark Construction | its website is clarkconstruction.com, your sub's |
| 16 | CLARK WATER | 7900 Westpark Dr, Mclean VA | possible | same | unsure |  | The results tie 7900 Westpark Drive in McLean to Clark Construction's new office, and repeatedly mention Clark Water only as having a separate office in Sterling, VA. No result ties Clark Water, LLC t |
| 17 | GUY F ATKINSON CONSTRUCTION | 611 Anton Blvd Ste 1100, Costa Mesa CA | possible | same | same | Guy F. Atkinson Construction, LLC | part of Clark Construction at clarkconstruction.com, your sub's website |
| 18 | SHIRLEY CONTRACTING | 8435 Backlick Rd, Lorton VA | possible | same | same | Shirley Contracting Company, LLC | The web page lists 'Clark Construction Group' as the parent of 'Shirley Contracting Company, LLC', making them affiliated companies rather than the same company. |
| 19 | CLARK CONSTRUCTION GROUP CALIF | 180 Howard St Ste 1200, San Francisco CA | excluded | same | same | Clark Construction Group - California, LP | its website is clarkconstruction.com, your sub's |
| 20 | CLARK CONSTRUCTION GROUP CALIF | 1390 Market St Ste 111, San Francisco CA | excluded | same | same | Clark Construction Group - California, LP | its website is clarkconstruction.com, your sub's |
| 21 | CLARK CONSTRUCTION GROUP CALIFORNIA | 18201 Von Karman, Irvine CA | excluded | same | same | Clark Construction Group - California, LP | its website is clarkconstruction.com, your sub's |
| 22 | CLARK CONSTRUCTION GROUP CALIFORNIA | 401 I St, Sacramento CA | excluded | same | unsure |  | No result ties 'CLARK CONSTRUCTION GROUP CALIFORNIA LP' to 401 I ST, Sacramento, CA 95814. Result [1] mentions Clark's presence in Sacramento but is a 2014 newsletter with no address and doesn't name  |
| 23 | CLARK CONSTRUCTION GROUP CALIFORNIA | 2233 Stockton Blvd, Sacramento CA | excluded | same | unsure |  | No result ties 'CLARK CONSTRUCTION GROUP CALIFORNIA LP' to 401 I ST, Sacramento, CA 95814. Result [1] mentions Clark's presence in Sacramento but is a 2014 newsletter with no address and doesn't name  |
| 24 | CLARK CONSTRUCTION GROUP CALIFORNIA | 180 Howard St Ste 1200, San Francisco CA | excluded | same | same | Clark Construction Group - California, LP | its website is clarkconstruction.com, your sub's |
| 25 | CLARK CONSTRUCTION GROUP CHICAGO | 216 S Jefferson St Ste 502, Chicago IL | excluded | same | same | Clark Construction Group - Chicago, LLC | its website is clarkconstruction.com, your sub's |
| 26 | CLARK CONSTRUCTION | 180 Howard St Ste 1200, San Francisco CA | excluded | same | unsure |  | No result ties an employer named 'CLARK CONSTRUCTION' to 135 Main St Ste 1120, San Francisco, CA 94105. Result [2] mentions 'Clark Construction Group LLC' with a clarkconstruction.com email but associ |
| 27 | CLARK CONSTRUCTION | 350 Indiana St Ste 600, Golden CO | excluded | same | same | Guy F. Atkinson Construction, LLC | The web page names Clark Construction Group, LLC as the parent of Guy F. Atkinson Construction, LLC, making them affiliated companies rather than the same entity. |
| 28 | CLARK CONSTRUCTION | 5353 West Alabama Ste 200, Houston TX | excluded | same | same | Clark Construction Group - Texas, LP | its website is clarkconstruction.com, your sub's |
| 29 | CLARK CONSTRUCTION | 135 Main St Ste 1120, San Francisco CA | excluded | likely | unsure |  | No result ties an employer named 'CLARK CONSTRUCTION' to 135 Main St Ste 1120, San Francisco, CA 94105. Result [2] mentions 'Clark Construction Group LLC' with a clarkconstruction.com email but associ |
| 30 | CLARK CONSTRUCTION | 1775 Dimond Dr, Juneau AK | excluded | different | different | CLARK CONSTRUCTION COMPANY | Clark Construction Group, LLC (Bethesda, MD) is a major national general contractor, while 'CLARK CONSTRUCTION COMPANY' with no parent named appears to be a distinct, similarly named firm, not identif |
| 31 | CLARK CONSTRUCTION | 1907 William Few Pkwy, Grovetown GA | excluded | different | unsure | Clark Construction Services, Inc. | The subcontractor is Clark Construction Group, LLC, while the OSHA-linked entity is Clark Construction Services, Inc.; the similar names alone do not establish whether they are the same, affiliated, o |
| 32 | CLARK CONSTRUCTION | 2660 Superior Ct, Auburn Hills MI | excluded | different | different | Clark Construction Company | it has its own website (clarkcc.com), not your sub's (clarkconstruction.com) |
| 33 | CLARK CONSTRUCTION | 3625 Moores River Dr, Lansing MI | excluded | different | different | Clark Construction Company | it has its own website (clarkcc.com), not your sub's (clarkconstruction.com) |
| 34 | CLARK CONSTRUCTION | 3535 Moores River Dr, Lansing MI | excluded | different | different | Clark Construction Company | it has its own website (clarkcc.com), not your sub's (clarkconstruction.com) |
| 35 | CLARK CONSTRUCTION | 3535 Moores River Dr, Lansing MI | excluded | different | different | Clark Construction Company | it has its own website (clarkcc.com), not your sub's (clarkconstruction.com) |
| 36 | CLARK CONSTRUCTION | PO Box 862, Madison MS | excluded | different | different | Clark's Construction, LLC | The subcontractor is Clark Construction Group, LLC of Bethesda, MD (clarkconstruction.com), while the OSHA-linked company is Clark's Construction, LLC; the names differ and no parent or ownership link |
| 37 | CLARK CONSTRUCTION | 1615 Apache Dr, Mccomb MS | excluded | different | different | Clark Construction, Inc. Of Mississippi | it has its own website (clarkinc.com), not your sub's (clarkconstruction.com) |
| 38 | CLARK CONSTRUCTION | 1615 Apache Dr, Mccomb MS | excluded | different | different | Clark Construction, Inc. Of Mississippi | it has its own website (clarkinc.com), not your sub's (clarkconstruction.com) |
| 39 | CLARK CONSTRUCTION | 1015 E Grand Blvd, Oklahoma City OK | excluded | different | different | Clark Construction, Inc. | it has its own website (clarkconstructioncompany.net), not your sub's (clarkconstruction.com) |
| 40 | CLARK CONSTRUCTION | 1700 N Paddington Trail, Sioux Falls SD | excluded | different | unsure | Clark Construction, LLC | the quote isn't on the page |
| 41 | CLARK CONSTRUCTION | PO Box 8, Lafayette TN | excluded | different | unsure |  | None of the results tie 'CLARK CONSTRUCTION COMPANY INC' to PO BOX 8, LAFAYETTE, TN 37083. The results reference several unrelated entities named Clark Construction (e.g., Clark Construction Group, a  |
| 42 | CLARK CONSTRUCTION | PO Box 10625, Bainbridge Island WA | excluded | different | unsure |  | No search result names the company. |
| 43 | CLARKE CONSTRUCTION | 45901 Arabia St, Indio CA | excluded | different | unsure |  | The only result is a 1966 Palm Springs area phone directory that contains 'MEREDITH & SIMPSON CONSTRUCTION C O Arabia&Hwylll Indio' and various entries named 'Clarke'/'Clark', but nothing names 'CLARK |
