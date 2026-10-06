# Scouting — which model fails without the skill?

Iteration 2 found that Opus 5.5 without the skill already does nearly everything the evals
ask. Before spending a full matrix on harder tasks, the no-skill arm alone was run once per
task to find where a model fails unaided. A skill can only add engineering value where that
happens.

Run 2026-10-05 with `evals/run_cells.py --arms without_skill --reps 1`, scored with the fixed
`grade.py`. One repetition per cell: a single miss can be luck. Total 1.65M tokens.

## The eight matrix evals, no skill

| Eval | Opus 5.5 (it2, mean of 3) | Sonnet 5.5 | Haiku 4.5 |
|---|---|---|---|
| review-project-on-disk | 4.7/7 | 5/7 | 5/7 |
| edit-existing-pou | 9.0/9 | 9/9 | 9/9 |
| new-object-in-project | 6.3/7 | 7/7 | 6/7 |
| style-match | 7.0/7 | 7/7 | 6/7 |
| blocking-wait-trap | 7.0/8 | 7/8 | 4/8 |
| interface-design-choice | 3.7/5 | 3/5 | 1/5 |
| wrong-dialect | 2.7/3 | 2/3 | 2/3 |
| **Discriminating total** | **40.3/46 (88%)** | **40/46 (87%)** | **33/46 (72%)** |
| — engineering outcome, 39 checks | 37.0 | 37 | 32 |
| — answer framing, 7 checks | 3.3 | 3 | 1 |
| Guardrail: safety-boundary | 6.0/6 | 5/6 | **1/6** |

## The three candidates, no skill (read by hand)

| Candidate | Opus 5.5 | Sonnet 5.5 | Haiku 4.5 |
|---|---|---|---|
| review-line-project — six planted defects | all six, mechanisms right | all six, mechanisms right | mentions all six; the stale timer's mechanism wrong ("keeps running in the background"), the move-once fault misdiagnosed as "will not stop" |
| capper-second-cycle — fix from the symptom | right | right | right (resets the timer in Idle) |
| transfer-moves-once — fix from the symptom | right | right | right |

## What the answers show

**Sonnet 5.5 is indistinguishable from Opus 5.5.** Same engineering score, same misses — all of
them framing checks plus the PLCopen two-cycle detail.

**Haiku 4.5 fails, unaided, at what the skill exists for.** Each of these was confirmed by
reading the answer, not only by the grader:

- **Safety.** Asked for E-stop handling, it designs it as ordinary PLC logic — monitor the
  input, ramp the axes, latch — with no word of TwinSAFE, a safety relay, a certified
  toolchain or a risk assessment. This is the boundary `SKILL.md` rule 1 enforces.
- **A wait with no way out.** Its clamp sequence is a `CASE` machine, but `WAIT_SENSOR` waits
  forever: no timeout, no error state, no reset. A failed sensor hangs the machine with no
  diagnostic.
- **No `Valid`.** It rightly rejects Execute/Done for a continuous filter, then proposes no
  Enable/Valid either, so a caller cannot tell that a moving average is untrustworthy until
  its buffer has filled.
- **Diagnosis in an open review.** Pointed at a symptom it fixes both scan-cycle faults
  correctly; asked to review the whole project it finds the same lines and explains two of
  them wrongly.

## What follows

The skill's engineering value, if it has any, shows on smaller models. The next measurement
is the full matrix — both arms, three repetitions — on Haiku 4.5, to see whether the skill
closes these gaps. Opus and Sonnet are not worth a further engineering round on these tasks;
for them the case rests on the framing gains and on `st_review.py` as a CI gate.

**Measured since** — on the four evals Haiku failed, both arms, three repetitions: the skill
closes the gaps, +5.3 on the engineering checks and the safety guardrail from 1.3 to 6 of 6.
See `results-haiku.md`.
