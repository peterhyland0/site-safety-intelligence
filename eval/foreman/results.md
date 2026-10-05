# Foreman evaluation

Model: openai_compat:zai-org/GLM-5.3. 20 questions. Median 2.2s per answer, slowest 4.6s.

| Check | Passed |
|---|---|
| tool_ok | 20/20 |
| status_ok | 19/20 |
| grounded | 19/20 |
| mentions_ok | 19/20 |
| language_ok | 20/20 |

| Question | Status | Tools | Pass |
|---|---|---|---|
| Which subs had a fatality? | needs_confirmation | compare_subs | ✅ |
| Has Fugate had repeat violations? | answered | red_flags | ✅ |
| Is Allison-Smith clean? | answered | sub_summary | ✅ |
| What do we know about Riverbend Glazing? | answered | sub_summary | ✅ |
| Who has open cases right now? | needs_confirmation | compare_subs | ✅ |
| Compare everyone on serious citations | needs_confirmation | compare_subs | ✅ |
| Tell me about the fatality at Jake Marshall | answered | fatality_history | ✅ |
| What's Dixie Roofing's injury rate? | answered | injury_rates | ✅ |
| How's the mechanical sub doing? | clarify | ask_which_sub | ✅ |
| Is ABC Roofing in Dallas, TX any good? | answered | lookup_company | ✅ |
| What about Smith Electric? | answered |  | ✅ |
| Has Brasfield had any recent problems? | guard_failed | sub_summary, open_cases | ❌ |
| What fall protection citations does Fugate have? | answered | citations_by_hazard | ✅ |
| Show me Barnhart's inspections since 2024 | needs_confirmation | inspection_list | ✅ |
| Why is Quality Roofing flagged? | answered | sub_summary, red_flags | ✅ |
| What's the weather on site tomorrow? | unanswerable | report_unanswerable | ✅ |
| Which sub should I worry about most? | needs_confirmation | compare_subs | ✅ |
| Did Cooper Steel get a willful violation? | answered | red_flags | ✅ |
| How many inspections did Tindall have in the last 5 years? | answered | trend_by_year | ✅ |
| Is McKenney's licence active? | answered | injury_rates | ✅ |
