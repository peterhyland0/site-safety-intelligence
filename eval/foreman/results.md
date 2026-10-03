# Foreman evaluation

Model: openai_compat:zai-org/GLM-5.3. 20 questions. Median 2.6s per answer, slowest 6.9s.

| Check | Passed |
|---|---|
| tool_ok | 20/20 |
| status_ok | 20/20 |
| grounded | 20/20 |
| mentions_ok | 20/20 |
| language_ok | 20/20 |

| Question | Status | Tools | Pass |
|---|---|---|---|
| Which subs had a fatality? | answered | red_flags | ✅ |
| Has Fugate had repeat violations? | answered | red_flags | ✅ |
| Is Allison-Smith clean? | answered | sub_summary, open_cases | ✅ |
| What do we know about Riverbend Glazing? | answered | sub_summary, red_flags | ✅ |
| Who has open cases right now? | answered | open_cases | ✅ |
| Compare everyone on serious citations | answered | compare_subs | ✅ |
| Tell me about the fatality at Jake Marshall | answered | fatality_history, red_flags | ✅ |
| What's Dixie Roofing's injury rate? | answered | injury_rates | ✅ |
| How's the mechanical sub doing? | clarify | ask_which_sub | ✅ |
| Is ABC Roofing in Dallas, TX any good? | answered | lookup_company | ✅ |
| What about Smith Electric? | answered |  | ✅ |
| Has Brasfield had any recent problems? | answered | sub_summary, inspection_list, open_cases, red_flags | ✅ |
| What fall protection citations does Fugate have? | answered | citations_by_hazard | ✅ |
| Show me Barnhart's inspections since 2024 | answered | inspection_list | ✅ |
| Why is Quality Roofing flagged? | answered | sub_summary, red_flags, compare_subs | ✅ |
| What's the weather on site tomorrow? | unanswerable | report_unanswerable | ✅ |
| Which sub should I worry about most? | answered | compare_subs, sub_summary | ✅ |
| Did Cooper Steel get a willful violation? | answered | red_flags | ✅ |
| How many inspections did Tindall have in the last 5 years? | answered | inspection_list | ✅ |
| Is McKenney's licence active? | answered | injury_rates | ✅ |
