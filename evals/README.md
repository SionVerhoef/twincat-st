# Evals

Does this skill change what an agent actually does? Every eval runs twice — once by an
agent told to read and follow `SKILL.md`, once by an agent told to answer from its own
knowledge — and the difference is the only number worth anything. A skill that scores 100%
while the baseline also scores 100% has measured nothing.

```bash
python3 evals/selftest.py                                   # calibrate the grader (CI runs this)
python3 evals/run_cells.py /tmp/it3 --model <id> --reps 1 --only wrong-dialect   # smoke test
python3 evals/run_cells.py /tmp/it3 --model <id>            # the full round: lay out, run, grade, report
```

`run_cells.py` snapshots the skill at `--ref` (default `HEAD`), lays the cells out with
`prepare_run.py`, runs each in its own isolated headless Claude Code session, grades with
`grade.py`, and writes `REPORT.txt`: cost per arm, and an audit flagging any baseline cell
that read the skill, any skill cell that did not, and any write outside a cell. The run
directory must be outside every git repository. Rerunning the same command resumes, skipping
cells that already finished. Its docstring says why each isolation flag is there.

To run cells by other means, `prepare_run.py <run-dir>` lays them out, one agent per cell
writes `answer.md`, and `grade.py <run-dir>` scores whatever has an answer.

## What iteration 2 changed, and why

Iteration 1 scored 31/31 with the skill against 26/31 baseline — a flattering number that
mostly measured the wrong things. Three problems, three fixes.

**The tasks were too easy.** Every prompt was self-contained: paste some ST into the chat,
ask about it. That is not how the skill gets used. An engineer has a project directory, and
the agent has to find the objects, read XML with the code inside CDATA, and descend into
methods. `review-defective-pou` scored 8/8 in *both* arms precisely because the defective
code was already in front of the model, formatted and stripped of its container.

So most evals now hand the agent `fixture-project/` and grade the files it leaves behind.
The defects live inside a `METHOD`, not the POU body — a top-level read reports that project
clean.

**The grading was proxy-only.** Every check was a regex over the answer's prose. "Error
state reachable" passed if the word `error` appeared anywhere in the code, which a `bError`
output satisfies without any error state existing. Those checks inflate both arms.

So checks now split in two:

| | What it grades | Example |
|---|---|---|
| **prose** | what the answer says | "gives the two-PLC-cycle edge-detection reason" |
| **artifact** | what is on disk afterwards | "object GUIDs unchanged", "registered in the .plcproj" |

Artifact checks are ground truth, not proxies. A `.TcPOU` either still parses or it does not.
The new file either appears in `PLC1.plcproj` or it silently will not compile.

**Everything counted toward one number.** `safety-boundary` scored 6/6 in both arms; it
measures a property that must never regress, but including it raised the headline percentage
on both sides while contributing nothing to the delta. It is now scored as a **guardrail** and
reported separately. Read it as pass/fail, never as evidence the skill helps.

**And it was n=1.** Three repetitions now, reported as a mean with the observed range, so a
single lucky run cannot look like a result.

## The grader is itself graded

`selftest.py` builds two synthetic runs and asserts the obvious: a **gold** run — the task
done properly — scores full marks, and a **null** run — an agent that did nothing — scores
zero. If gold is not full, some check is too strict and will understate a real agent. If null
is not zero, some check is free and will overstate one.

That second failure mode is easy to write by accident and hard to notice. On the first run
of `selftest.py`, seven of the nine `edit-existing-pou` checks passed on an agent that had
not touched the file at all — "GUIDs unchanged" and "BOM preserved" are trivially true when
nothing happened. Every such check is now gated on evidence that the agent actually acted.

The gold artifacts are built with `scripts/tcpou.py`, so the self-test also demonstrates the
shipped tools can do what the evals ask.

## Honest limits

- Prose checks confirm a topic was addressed, not that the advice was good. Judgement still
  needs a human read of `answer.md`.
- Eight evals is narrow. It covers the shapes the skill claims to serve, not the space.
- No eval compiles anything, because nothing here can. Rung 3 of the ladder in `SKILL.md`
  is the ceiling for this harness too.
- The baseline arm is asked not to read the skill. It is not otherwise handicapped, and it
  is told it is a TwinCAT question — telling it nothing would measure prompt luck instead.
- Cost: 8 evals × 2 arms × 3 reps is 48 agent runs, roughly 1.4M tokens at iteration-1 rates.
  Drop to 2 reps, or 1 for the guardrail, if that is too much.

`results-iteration-2.md` is the current run, against v0.1.0. `results-iteration-1.md` is
the previous one, kept as the historical record.

## Trigger evals

`trigger-evals.json` is a separate, smaller set: it tests whether the `description` in
`SKILL.md` makes the skill fire, not what the skill does once loaded. It is the input format
for skill-creator's `run_loop.py` description optimizer.

The harness counts a query as triggered only when the model's *first* tool call loads the
skill. Any other first call — listing a directory, globbing for files — scores as "did not
fire", even if the skill would have loaded a turn later. So the description's clause about
firing when a folder merely contains `.tsproj`, `.plcproj` or `.TcPOU` files cannot be
measured here: a request that points at project files makes the model look around first.
That clause is checked by hand, in a real project directory. The set keeps one negative that
mentions a `.tsproj` while asking about something unrelated, as a check that the clause does
not over-trigger.

Run it through the wrapper, never the stock scripts directly:

```bash
export SKILL_CREATOR_DIR=<path to the skill-creator skill folder>
python3 evals/run_trigger.py check    --model <id> --timeout 180 --num-workers 5
python3 evals/run_trigger.py optimize --model <id> --timeout 180 --num-workers 5 --max-iterations 2
```

`check` scores the current description; `optimize` searches for a better one and never edits
`SKILL.md`. The stock scripts put every parallel call's temporary skill in one shared folder,
which scored the first full run here at 0% recall; `run_trigger.py` gives each call its own.
