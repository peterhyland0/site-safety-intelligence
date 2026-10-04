# The match adjudicator: why it uses Jev

**Decision (October 2026).** Uncertain OSHA matches without red flags are decided by **Jev 1.13**, TypeSafe AI's
decision model. Red-flagged ones stay with **DeepSeek V4.1 Flash**, because the GC reads its reason. On a
held-out sample Jev excluded more lookalikes (130 against 110) with fewer mistakes (9 wrong exclusions against
13, no wrong merges against 2), in a quarter of the time, for about a cent a run.

It's on whenever `JEV_API_KEY` is set. `SSI_ADJUDICATOR=llm` sends everything back to the LLM.

Code: [ssi/llm/jev.py](../ssi/llm/jev.py) (client, thresholds, reason line) and
[ssi/llm/adjudicator.py](../ssi/llm/adjudicator.py) (routing). Evaluation: [eval/adjudication/](../eval/adjudication/).

---

## What the adjudicator does

A GC types a sub's name. OSHA records carry no company ID, so the matching rules sort every candidate record
into matched, possible or excluded ([README §3](../README.md#3-matching-subs-to-osha-records)). The records the
rules can't settle are grouped by name and state, and each group goes to the adjudicator with an evidence packet:
the GC's input, the records already matched, and the candidates. It sees identity evidence only, never safety
history.

The answer sets the group's bucket:

| Answer | Effect |
|---|---|
| Same company, confident | **matched**: counted in the sub's scorecard |
| Different company, confident | **excluded**: not counted, listed under excluded |
| Otherwise | **possible**: not counted, shown as possible |
| Any answer on a red-flagged group | **possible**, and a yes/no question to the GC with the AI's lean and reason |

So a wrong merge (someone else's history attached to the sub) is the worst error, a wrong exclusion (the sub's
own history hidden) is next, and a lookalike left possible costs only clutter.

## What Jev is

Jev is a "System One" model. It takes some state and typed questions, and returns a label with a probability for
each option, in 70–500 ms. It doesn't generate text. It was released on 15 September 2026 and costs $0.042 per
million input tokens; output is free.

The app asks it one question per group, a choice of same / different / unsure. The instructions are the same
guidance the LLM gets ([`GUIDANCE`](../ssi/llm/adjudicator.py)), and the state is the same evidence lines.

## How the two were compared

[eval/adjudication/run.py](../eval/adjudication/run.py) grades both on silver labels taken from OSHA's injury
filings, which carry the employer's tax ID:

- **Same company:** two OSHA records that link to the same tax ID.
- **Different company, same state:** the same name core and state, different tax IDs.
- **Different company, other state:** the same name core in two states, different tax IDs, each filing in one
  state only. This leaves out national firms that file under several tax IDs, the main source of wrong labels.

Each pair is searched the way a GC would, and only the pairs the rules leave uncertain go to the adjudicators.
Both get the packet the app would build, and their answers go through the app's thresholds.

The cross-state set was added after the first round. Without it every cross-state pair was the same company,
so the guidance's "a common name in a different state is usually a different company" could only be shown to
cost, never to save.

Jev's thresholds were picked on a **development sample** (seed 7, 302 uncertain pairs) and frozen. They were
then checked on a **held-out sample** (seed 11, 246 uncertain pairs) that shares no pair and no search with it.

## Results

Held out ([full table](../eval/adjudication/results-seed11.md)); outcomes as matched · possible · excluded:

| Pairs | n | DeepSeek V4.1 Flash | Jev, as the app uses it |
|---|---|---|---|
| Different company, same state | 62 | 2 · 39 · 21 | 0 · 20 · **42** |
| Different company, other state | 110 | 0 · 21 · 89 | 0 · 22 · 88 |
| Same company, same state | 16 | 4 · 11 · 1 | 0 · 16 · 0 |
| Same company, other state | 58 | 0 · 46 · 12 | 0 · 49 · **9** |
| **Wrong merges / wrong exclusions** | | **2 / 13** | **0 / 9** |
| Lookalikes excluded | 172 | 110 | 130 |
| AUC of P(same) | | 0.77 | 0.84 |
| Median time per group | | 0.8 s | 0.23 s |

Development sample ([full table](../eval/adjudication/results.md)):

| Pairs | n | DeepSeek V4.1 Flash | Jev, as the app uses it |
|---|---|---|---|
| Different company, same state | 111 | 1 · 57 · 53 | 0 · 32 · 79 |
| Different company, other state | 104 | 0 · 20 · 84 | 0 · 29 · 75 |
| Same company, same state | 21 | 1 · 19 · 1 | 0 · 20 · 1 |
| Same company, other state | 66 | 0 · 58 · 8 | 0 · 64 · 2 |

## Why Jev

1. **More accurate where it acts.** On the held-out sample it excluded 20 more lookalikes, and wrongly excluded
   4 fewer of the sub's own records.
2. **No wrong merges.** DeepSeek's two merged corporate families under different tax IDs (Barton Malow and
   Barton Malow Builders; Stellar Contracting and Stellar Group). Jev's P(same) never reached the 0.85 needed to
   match.
3. **It separates same from different better** (AUC 0.84 against 0.77). DeepSeek's stated confidence comes in a
   few round numbers (0.80, 0.85, 0.90), so there's little to tune.
4. **About 3.5× faster** (0.23 s against 0.8 s a group), which shortens the "Resolving N uncertain records…" wait
   on the project page.
5. **Nothing to make up.** Jev returns probabilities for fixed labels. DeepSeek's written reasons need a
   validator (cited evidence must exist, every name and number must appear in the evidence), which rejected 1–6
   answers a run. Those groups stay undecided.
6. **Cost.** About a cent of Jev for a 250-group run (307k input tokens), with no GPU to host.

## What it gives up, and how that's handled

- **No written reason.** Jev's reason line is written in code from the evidence, so every fact in it is true by
  construction. Each fact is listed as for or against the same company, the side that agrees with the verdict
  first, so a fact that points the other way reads as weighed rather than as a contradiction. For example:
  > Likely a different company: Jev puts the chance it's the same company at 4%. Against: Las Vegas, NV, outside
  > the sub's state (OK); no address in common with the sub's matched records. For: same trade code (2371).

  A shared trade code is real but weak evidence: in the held-out sample 80% of same-company pairs shared the sub's
  code, but so did 34% of the lookalikes, and the pairs that shared one split 59 same, 58 different. (This
  example is NPL Construction, a national firm: the "for" side was right, and it's one of the wrong exclusions
  below.)
- **Red-flagged groups stay on DeepSeek.** They're the one place a person reads the AI's reasoning to decide,
  about 1 group in 10 (23 of 246 held out). Without an LLM configured, Jev takes them too, with the same code-written
  reason.
- **It never matches.** A same-company record Jev isn't sure of stays possible, which isn't counted. DeepSeek
  matched 4 such records held out, alongside its 2 wrong merges.
- **A national firm's branches in other states.** These are the wrong exclusions that remain: NPL Construction
  six times, NVR twice, PAR Electrical once (9 of 58 held out, against DeepSeek's 12). A check in the app for
  "NPL Construction, Tulsa" excluded its records in Nevada, Pennsylvania and California the same way. Both models
  follow the guidance's different-state rule, which is right far more often than wrong (88 lookalikes against 9
  branches held out). Telling the adjudicator whether a name is distinctive, which the rules already know, may
  separate the two for either model.
- **The other-state threshold looked better than it was.** Wrongly excluded branches went from 2 of 66 on the
  development sample to 9 of 58 held out. The same-state threshold held exactly.
- **Its probabilities aren't calibrated on this task** (Brier 0.20 against DeepSeek's 0.17), so the thresholds
  are empirical cut-offs, not "4% means 4%".
- **A third party sees the evidence.** The packet, including the sub names a GC types, goes to TypeSafe, which
  publishes no retention policy. Use TypeSafe's own API (`api.typesafe.ai`, the default): lookalike sites resell
  Jev access through their own servers.
- **A young, closed model.** TypeSafe offers only aliases (`jev-latest`, `jev-preview`), so a new version arrives
  without notice. Every decision records the version that made it (`decided_by = ai:jev:jev-1.13.0`), and the
  app logs a warning when a version other than 1.13 answers.

## How it runs

```
uncertain group ─► red flags? ── yes ─► DeepSeek (LLM): checked written reason; GC question
                        │
                        no
                        ▼
                  Jev, JEV_API_KEY set? ── no ─► DeepSeek, or left possible without an LLM
                        │
                        yes
                        ▼
              P(same) ≥ 0.85            → matched
              P(same) ≤ 0.20, same state  → excluded
              P(same) ≤ 0.06, other state → excluded
              otherwise                 → possible
              (a failed Jev call falls back to DeepSeek)
```

P(same) is Jev's probability for "same" plus half its probability for "unsure". Answers are cached in
`app.adjudication_cache`, keyed on the model, the question and the evidence, and count toward the daily token
budget like the LLM's.

**Settings:** `JEV_API_KEY` (from console.typesafe.ai/keys), optional `JEV_API_URL`, and `SSI_ADJUDICATOR=llm`
to switch Jev off. On Modal, the `ssi-jev` secret with `SSI_WITH_JEV=1` ([deploy guide](deploy.md)).

## Larger LLMs (GLM 5.3, Kimi K3)

Run afterwards on the same samples, with the LLM adjudicator's prompt and checks
([README, evaluation](../README.md#8-evaluation)). Held out, wrong merges / wrong exclusions / lookalikes excluded:
DeepSeek 2 / 13 / 110, **GLM 5.3 0 / 2 / 98**, Kimi K3 2 / 2 / 111, Jev 0 / 9 / 130.

The larger models mostly fix the national-branch weakness, but they clear fewer lookalikes. They're 10–30× slower
(p90 around 20 s a group), and about 1 answer in 10 fails the checks. Kimi K3 also merged 2 different companies.
The best result so far is a split: Jev in the sub's state, GLM 5.3 outside it (held out 2 wrong exclusions, no
wrong merge, 125 lookalikes excluded). It was found after the held-out run, so it needs a fresh sample before the
app adopts it.

## When to look again

Re-run `make eval-adjudication` (answers are cached, so it only pays for new ones) when:
- the app logs a new Jev version;
- the guidance or the evidence packet changes;
- the matching rules change what reaches the adjudicator (for example rule M3, which auto-matches different
  firms that share a distinctive name across states; see the README's evaluation section).
