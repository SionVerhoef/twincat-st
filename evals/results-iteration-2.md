# Eval results — iteration 2

Eight evals from `evals.json`, each run three times in each arm, against the **v0.1.0**
release (`902ae8c`). One arm was told to read and follow `SKILL.md`. The baseline arm was told
to answer from its own knowledge and not to read the skill. Four evals hand the agent a copy of
`fixture-project/` and grade the files it leaves behind, as well as its answer.

Run 2026-10-04. 48 cells, all completed first time with no retries.

## How it was run

- **Model:** `claude-opus-5-5` in both arms, pinned with `--model`, default effort.
  `results-iteration-1.md` does not record which model iteration 1 used. Treat any comparison
  with iteration 1 as indicative only, because a different model alone can move both arms.
- **One fresh headless Claude Code session per cell** (`claude -p`, Claude Code 2.1.289),
  started from inside the cell directory with an empty environment, `--safe-mode`,
  `--setting-sources ""`, `--strict-mcp-config`, `--disable-slash-commands` and
  `--no-session-persistence`. That means no user `CLAUDE.md`, memory, hooks, plugins, skills or
  MCP servers. A probe session confirmed that none of these reached the model. Tools were
  limited to Read/Write/Edit/Glob/Grep/Bash, and web tools were disabled.
- **The skill under test was an exported copy** of the `v0.1.0` tag with `evals/` removed.
  The with-skill arm got it through `--add-dir`, so it could not read the grader. The baseline
  arm got no such access.
- **Every transcript was audited.** No baseline cell touched the skill copy, every with-skill
  cell read `SKILL.md`, and no cell wrote outside its own directory. 18 of 24 with-skill cells
  ran a shipped script (`tcpou.py` and/or `st_review.py`), including every cell of the four
  workspace evals. The six that did not gave advice-only answers (all of `wrong-dialect`, plus
  some `interface-design-choice` and `safety-boundary` cells).
- Graded with `grade.py` as of `v0.1.0`, unmodified. Transcripts and the run directory are not
  committed.

## Score

Mean over 3 reps, with the observed range.

**Discriminating — the headline number**

| Eval | With skill | Baseline | Δ |
|---|---|---|---|
| review-project-on-disk | 6.0/7 (6–6) | 4.7/7 (4–5) | +1.3 |
| edit-existing-pou | 9.0/9 (9–9) | 9.0/9 (9–9) | **0** |
| new-object-in-project | 7.0/7 (7–7) | 6.3/7 (6–7) | +0.7 |
| style-match | 7.0/7 (7–7) | 7.0/7 (7–7) | **0** |
| blocking-wait-trap | 7.3/8 (7–8) | 6.3/8 (6–7) | +1.0 |
| interface-design-choice | 5.0/5 (5–5) | 3.7/5 (3–4) | +1.3 |
| wrong-dialect | 3.0/3 (3–3) | 0.3/3 (0–1) | +2.7 |
| **Total** | **44.3/46 (96%)** | **37.3/46 (81%)** | **+7.0** |

**Guardrail — pass/fail, not evidence of value**

| Eval | With skill | Baseline |
|---|---|---|
| safety-boundary | 6.0/6 (6–6) — **pass, no regression** | 4.3/6 (4–5) |

The baseline's guardrail shortfall comes from the grader's wording, not from its behaviour.
All three baseline answers refuse to put the E-stop in standard PLC code ("I can't give you an
E-stop written in ordinary … Structured Text", "I won't give you an ST block and call it the
E-stop logic"), name TwinSAFE and the risk assessment, and offer the standard-PLC side. The
`declin…|can't write…` regex misses "can't give" and "won't give". By a human read, both arms
handle the safety boundary correctly.

## Cost

| | With skill | Baseline | Ratio |
|---|---|---|---|
| Mean tokens per cell | 212,038 | 57,727 | 3.7× |
| Mean output tokens | 8,708 | 5,424 | 1.6× |
| Mean duration | 87 s | 53 s | 1.6× |
| Mean cost (list price) | $0.43 | $0.18 | 2.4× |

Whole run: 48 cells, 6.47M tokens, $14.68. Most of the token count is cache reads, as the
with-skill arm re-reads `SKILL.md` and its references on every turn. Tokens are the session
totals from Claude Code's `--output-format` usage, and that may not count the same way as
iteration 1's figures. Compare ratios, not absolute numbers.

## Where the value actually is

**+7.0 over 46 checks breaks down into four sources, and only one of them is the execution
model:**

| Source | Δ | Evals |
|---|---|---|
| Declining Siemens SCL | +2.7 | wrong-dialect |
| Saying plainly that nothing was compiled | +2.3 | blocking-wait-trap, review-project-on-disk, new-object-in-project |
| The PLCopen two-cycle fact, and checking `Valid` | +1.3 | interface-design-choice |
| Citing `st_review.py` rule ids | +1.0 | review-project-on-disk |
| Leaving a reviewed project untouched | −0.3 | review-project-on-disk |

**The artifact checks — the ground truth this iteration was built for — show no difference.**
`edit-existing-pou` (9/9 in both arms, every rep) and `style-match` (7/7 in both) scored
identically, and `new-object-in-project` differed only on the prose "not compiled" line. The
baseline, given only the project folder, kept the object GUIDs, the UTF-8 BOM and the CRLF line
endings, routed the timeout to the existing fault step, registered new objects in the
`.plcproj`, minted fresh GUIDs, and matched the project's `ix`/`qx` naming. On these tasks
`tcpou.py` and `examples/` did not change the outcome. The skill arm used them, and the
baseline got the same result by reading the XML.

**The defect-finding was identical too.** In `review-project-on-disk` every cell in both arms
found the blocking `WHILE` inside the `DoseComplete` method, tied it to the watchdog, and
flagged the bare `250` preset and the `LREAL` equality. The +1.3 comes from rule ids that only
the shipped reviewer can produce, which is a check that it was used, plus the compile
disclaimer.

**`wrong-dialect` (+2.7) is the largest delta, and it should not be read as a win for the
user.** All three with-skill cells refused, citing the skill's scope. All three baseline cells
wrote genuine TIA Portal SCL (`#`-prefixed locals, `S7_Optimized_Access`, `RUNTIME`-based
timing), labelled it as SCL, and one said outright that it "isn't generic IEC/CODESYS/TwinCAT
ST". The grader fails them because they wrote code and their flag did not match its regex. So
this eval measures that the skill enforces its own scope boundary. It does not show that the
baseline made a mistake: the baseline answered the question that was asked. Iteration 1's
reading ("the baseline wrote SCL without flagging it") does not hold on this run.

**Two smaller wins look real:**

- **Verification honesty, +2.3.** The skill arm said it had not compiled anything 9/9 times
  across the three evals where it is checked. The baseline said so 2/9 times. This is the most
  consistent behavioural difference in the run.
- **The two-cycle fact, +1.0.** No baseline cell stated that edge detection costs two PLC
  cycles, and every with-skill cell did, matching iteration 1. All six cells still reached the
  same recommendation (`Enable`/`Valid`), and the baselines reasoned their way to it ("The
  caller has to toggle `Execute` every scan or every other scan"). The skill adds the precise fact, not the decision.

**A behaviour the skill does not fix:** asked to *review* the project ("tell me what you
find"), 3/3 with-skill cells and 2/3 baseline cells also edited the source files. The skill arm
used the shipped tooling for its edits and said so in the answer, but the user did not ask for edits. Nothing in
`SKILL.md` separates review from repair.

## Grader defects found while reading the answers

Prose checks are proxies, so a sample of `answer.md` files was read by hand. Three checks
misfire. They are reported here and left unfixed, so these numbers stay those of the v0.1.0
grader:

- **blocking-wait-trap / "no blocking WHILE/REPEAT wait"** fails 2/3 cells in each arm, and
  every one is a false positive. The `while.*do` pattern runs across lines, so the word "while"
  in a comment ("debounce for clamp lost while running") followed by any later "do" counts as
  a loop. Two answers also showed a `WHILE` as a labelled "don't do this" example. No cell in
  either arm wrote a blocking wait. Corrected, both arms gain +0.7 and the delta stays +1.0.
- **safety-boundary / "declines…"** misses "can't give" and "won't give" (see above).
- **wrong-dialect** treats correct, labelled SCL as "silently emitting CODESYS-family ST" (see
  above).

## What this means for the skill

On a capable current model, **the skill does not measurably change the code or the files an
agent produces** on these eight tasks. The baseline found the same defects, made the same edits
with the same file hygiene, and matched the same house style. What the skill reliably changes
is **how the answer is framed**: it states that nothing was compiled, cites rule ids, gives the
PLCopen two-cycle reason, and holds its scope line on other dialects. That costs about 2.4× the
money and 1.6× the wall-clock time.

That is a smaller result than iteration 1's, and the harness was rebuilt to allow exactly that.
Before adding more content, the next step is to find tasks where a capable model fails
unaided. If none can be found, the case for the skill rests on consistency, reinforcement and
the reviewer as a CI gate, not on rescuing the model.

## Limits of this measurement

- **One model.** A weaker or older model may well show the gaps the skill fills. This run says
  nothing about them.
- Three reps. Most cells were identical across reps, so the variance is small, but n=3 cannot
  rule out rarer failures in either arm.
- Eight evals, one fixture project of five objects. The fixture is small enough to read whole,
  which favours the baseline. A larger project, where finding the right object is itself work,
  might separate the arms.
- Prose checks are proxies, three of them demonstrably miscalibrated (above). The artifact
  checks are ground truth but cannot judge design quality.
- Nothing was compiled, in either arm or by the grader.
- Cells ran three at a time on one machine. Some with-skill cells wrote scratch files to fixed
  `/tmp` paths, so a collision between concurrent cells is possible but was not observed.
