# Rule M3 audit: findings (Phase 0)

Automated verdicts: [results.md](results.md) (eval/m3_audit/run.py, Tavily profiles, 146 searches). This page adds a
hand review and what it means for tightening M3.

## What the web says

| M3 matches | n | same | different | unknown |
|---|---|---|---|---|
| Tax IDs say different (one pair per name, every such name) | 55 | 14 | 21 | 20 |
| Tax IDs say same (sample) | 25 | 21 | 0 | 4 |
| The app's own M3 matches | 21 | 19 | 0 | 2 |

- **The check is safe:** on the 46 matches known to be right (tax-ID same, and the app's), it never says
  "different".
- **The tax-ID "different" set is a third the same company:** national firms that file each state under its own tax
  ID (Tutor Perini, Alston, Conti, DN Tanks, Contrack Watts, Knife River). Unsettled ones include more of these
  (D.R. Horton, Katerra, J.F. Shea), so the earlier "M3 wrongly merges 3% of cross-state pairs" overstated it.
- **Hand review of the 21 "different":** 19 are clear (Ames in PA vs Ames in MN, Quinn, Procon, Huff, Gunter, Melton
  Electric, Haskins, K2, …). Two are doubtful: STEELCON (B's search found another firm, hodge.co) and MASONOMICS (two
  Masonomics domains). Among the unknowns, CITY OF PORTLAND (Maine against Oregon) and STRAUB CONSTRUCTION are clearly
  different too.
- **Size of the problem:** about 20 wrong names out of about 260 cross-state M3 names with tax-ID data (≈ 8% of
  names), far less by records, since national firms carry most of them. In the app: none of 21.

## What the wrong ones have in common

Small firms whose names collide across states. Their footprint is no different from correct matches (median 4
states either way; 4 against 6 establishments), so a footprint threshold can't separate them. Two features lean:

| | Wrong (21) | Right (35) |
|---|---|---|
| Same trade code | 6 | 20 |
| Name ends CONSTRUCTION / ELECTRIC | 14 | 8 |
| **Different trade and "<word> CONSTRUCTION/ELECTRIC"** (2 words) | **10** | **1** (Gibraltar Construction) |

## Options for Phase 1

- **A. Narrow guard, no web needed:** M3 becomes possible (not matched) when the trade codes differ and the name is one
  word plus CONSTRUCTION or ELECTRIC. Here it catches 10 of 21 wrong matches and sends 1 of 35 right ones to the
  adjudicator. Instant and free, but tuned on 56 matches: check it on a fresh sample first.
- **B. Web check when a profile exists:** for an M3 record in a state the sub's profile doesn't list, profile the
  record's own company (one Tavily search a state); a different company website moves it to possible. Here it catches
  all 21 and loses none of the 46 right ones; it needs the lookup on and costs a search per unlisted state.
- **A + B:** the guard always, the web check when the lookup is on.

## Built (Phase 1: A + B)

- **A, the guard** (`rules.m3_collides`, applied in `run.match` before the address expansion, rule **M3u**): re-running
  the audit's 101 matches through the rules, it holds back 10 of the 21 web-confirmed wrong matches, 6 of the 20
  unknown, and 3 of the 54 right ones (Gibraltar, Oftedal and Pavilion Construction; none from the app or the tax-ID
  "same" sample). `scripts/rematch` dry run on the app's three projects: no decision changes.
- **B, the web check** (`adjudicate.check_m3`, rule **M3w**): with a profile, an M3 group in an unlisted state has its
  company looked up; another website sends it to the adjudicator, the sub's own website confirms it. It also restores
  a guarded M3u record when the profile lists its state or the lookup finds the sub's website, which covers the three
  right ones the guard held back whenever a profile exists. Runs in `resolve`, the "Look up this company" button and
  `scripts/rematch`.
