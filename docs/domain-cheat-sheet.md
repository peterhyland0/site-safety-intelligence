# Construction safety cheat sheet

Domain terms for Site Safety Intelligence. Penalty figures and the BLS average are approximate, and the citation codes still need checking against the actual data.

## People
| Term | Meaning |
|---|---|
| **Owner** | Whoever is paying for the building, such as a developer or a hospital. |
| **GC (general contractor)** | Holds the contract with the owner and runs the whole job. The customer for this project. |
| **Sub (subcontractor)** | A trade company the GC hires: roofer, electrician, concrete. The GC brings 10–15 of them. |
| **Foreman** | Runs the crews on site day to day. Asks questions from a phone. |
| **Superintendent ("super")** | The GC's senior person on site, above the foremen. |
| **Safety manager / EHS** | Owns safety at the GC. EHS means environment, health and safety. Often the person who actually vets subs. |

## The process
| Term | Meaning |
|---|---|
| **Bid** | The GC's price for the job. Subs bid to the GC for their trade's piece. |
| **Prequalification ("prequal")** | Vetting a sub before letting them bid or work: safety record, insurance, finances. **This is what the project builds.** |
| **Controlling employer** | OSHA's rule that the GC can be cited for a sub's hazard on a shared site. It's the main reason GCs care about subs' safety. |
| **Prequal platforms** | ISNetworld, Avetta, Highwire and Autodesk's TradeTapp. The existing products in this space. |

## OSHA basics
| Term | Meaning |
|---|---|
| **OSHA** | The Occupational Safety and Health Administration, the federal workplace safety agency in the Department of Labor, created in 1970. |
| **State plans** | About 20+ states run their own OSHA-approved programs, such as Cal/OSHA. Their inspections are in the same data, and `reporting_id` shows which office did each one. |
| **29 CFR 1926** | The construction rulebook. Part 1910 is general industry. |
| **Most-cited construction rules** | `1926.501` fall protection (#1 overall for years), `1926.1053` ladders, `1926.451` scaffolding, `1926.503` fall protection training, `1926.102` eye and face protection. |
| **General Duty Clause, 5(a)(1)** | A catch-all for serious hazards with no specific rule, such as heat. |
| **"Fatal Four"** | The four causes of most construction deaths: falls, struck-by, electrocution, caught-in/between. |
| **SVEP** | The Severe Violator Enforcement Program, OSHA's public list of the worst repeat offenders. A sub on it is a major red flag. |

## Why OSHA shows up
Main reasons: a **fatality or catastrophe**, a **worker complaint**, a **referral** from another agency, a **planned or programmed** visit targeting high-hazard work (construction is one), or a **follow-up** to check fixes.

The `insp_type` column records this, as letter codes. Decode them from the data dictionary rather than from memory.

## Citation types (`viol_type`)
| Code | Meaning | How worried to be |
|---|---|---|
| **W** Willful | Knowingly ignored the rule | 🔴 Very |
| **R** Repeat | Cited for the same thing before | 🔴 Very: they didn't learn |
| **S** Serious | Could cause death or serious harm | 🟠 Common in construction; the rate matters more than the count |
| **O** Other-than-serious | Paperwork or minor | 🟢 Low |
| **U** Unclassified | Often the result of a settlement: the employer pays but drops the willful label | 🟠 Look closer |
| **FTA** Failure to abate | Didn't fix a cited hazard (the `fta_*` columns) | 🔴 Very |

Confirm these letters in the data while profiling.

## What happens after a citation
- **Initial vs current penalty.** Penalties are often cut in an **informal settlement**, so compare `initial_penalty` with `current_penalty`.
- **Contest.** The employer can fight the citation before the **OSHRC** (the review commission). It may be reduced or vacated.
- **Abatement.** Fixing the hazard.
- **Final order.** The citation is no longer appealable.
- **Deleted citations** (`delete_flag`) shouldn't be counted.
- **Maximum penalties** are adjusted for inflation each year. 2025: roughly **$16.5k** per serious violation and roughly **$165k** per willful or repeat one.

## The safety scores GCs actually use
| Metric | What it is | Public? |
|---|---|---|
| **TRIR** (total recordable incident rate) | Injuries per 100 full-time workers: recordable cases × 200,000 ÷ hours worked. 200,000 hours is 100 people × 40 hours × 50 weeks. Construction averages in the low 2s. | Partly, through OSHA's published injury-rate data |
| **DART rate** | Same formula, counting only cases with days away, restricted duty or a job transfer | Same |
| **EMR** (experience modification rate) | The workers' comp insurance multiplier. 1.0 is average and above 1.0 is worse. Many GCs require 1.0 or below. | ❌ The sub provides it |
| **OSHA 300 / 300A** | The injury log a company must keep, and its yearly summary. Larger construction firms submit the 300A electronically, and OSHA publishes it. **Likely the "other public data" hint, because it includes hours worked.** | ✅ |

## Data terms
| Term | Meaning |
|---|---|
| `activity_nr` | Inspection ID. Every table joins on it. |
| `estab_name` | Company name as written on that inspection. **There's no company ID**, which is the core messiness. |
| `site_*` vs `mail_*` | Job-site address vs company mailing address. For construction, `mail_*` is the more stable one. |
| **NAICS / SIC** | Industry codes, new and old. Construction is NAICS **23**, SIC **15–17**; most subs are NAICS **238**. |
| Open vs closed case | Open means citations may still change. |
