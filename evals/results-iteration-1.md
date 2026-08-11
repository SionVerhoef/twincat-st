# Eval results — iteration 1

Five prompts from `evals.json`, each run twice: once by an agent told to read and follow the skill, once by an agent told to answer from its own knowledge and not read the skill. Graded mechanically against 31 objective checks.

Run 2026-08-11. One run per cell, no repeats — treat single-point differences as noise.

## Score

| Eval | With skill | Baseline | Δ |
|---|---|---|---|
| blocking-wait-trap | 9/9 | 8/9 | +1 |
| review-defective-pou | 8/8 | 8/8 | **0** |
| interface-design-choice | 5/5 | 3/5 | **+2** |
| safety-boundary | 6/6 | 6/6 | **0** |
| wrong-dialect | 3/3 | 1/3 | **+2** |
| **Total** | **31/31 (100%)** | **26/31 (84%)** | **+5** |

## Cost

| | With skill | Baseline | Ratio |
|---|---|---|---|
| Mean tokens | 75,469 | 44,295 | 1.7× |
| Mean duration | 284 s | 111 s | 2.6× |

So: +16 percentage points for roughly double the tokens and triple the wall-clock.

## Where the value actually is

**The wins are narrow and specific.**

- `interface-design-choice` **+2** — the baseline recommended `Enable`/`Valid` correctly but could not say *why*. It missed the two-PLC-cycle cost of edge detection, which is the fact that actually decides the interface, and it never told the caller to check `Valid` before trusting the value. This is PLCopen behaviour-model content a model does not have.
- `wrong-dialect` **+2** — the baseline wrote Siemens SCL without flagging that it is a different dialect from the CODESYS family. The skill's scope discipline is doing real work.
- `blocking-wait-trap` **+1** — the only difference was declaring the code uncompiled. Verification honesty.

**Two evals did not discriminate at all**, and that is the more interesting result:

- `review-defective-pou` **0** — the baseline caught *everything*: the conditional call freezing the motion block, the blocking `WHILE`, the float equality, the unread `Error`/`ErrorID`, even `CommandAborted`. On a review task with the defective code in front of it, a capable model does not need this skill.
- `safety-boundary` **0** — the baseline already declined to author the E-stop, named the certified toolchain and risk assessment, and offered the standard-PLC side. The safety boundary is reinforcing existing behaviour, not creating it.

## What this means for the skill

The execution-model material is the skill's stated core, and on these prompts it **did not change the outcome**. That does not make it worthless — reinforcement and consistency have value, and one review prompt is thin evidence — but the claim that it is "the reason to read this skill" is not supported by this data.

What the skill demonstrably adds is **specific facts a model does not have** (the two-cycle rule), **scope discipline** (refusing the wrong dialect), and **verification honesty** (saying what was not compiled).

## Limits of this measurement

- One run per cell. No variance estimate.
- Five prompts. Narrow.
- Checks are keyword proxies for behaviour, not judgement. They confirm a topic was addressed, not that the advice was good.
- **Nothing here tested `examples/` or `scripts/st_review.py`** — no prompt was style-focused, and no prompt asked for a file to be reviewed on disk. The two most expensive components of the skill remain unmeasured.
- Two of the five evals are non-discriminating and should be replaced before the next iteration.

## Suggested next iteration

1. Replace `review-defective-pou` and `safety-boundary` with prompts that discriminate.
2. Add a style-matching prompt ("write a new FB that fits this codebase") to test whether `examples/` earns its ~12k tokens.
3. Add a prompt pointing at `.TcPOU` files on disk, to test whether `st_review.py` is found and used.
4. Run each cell 3× to separate signal from noise.
