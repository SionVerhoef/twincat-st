#!/usr/bin/env python3
"""Lay out a run directory: one folder per eval / arm / repetition, each with the
exact prompt and, where the eval needs one, a pristine copy of the fixture project.

    python3 evals/prepare_run.py [run-dir] [--reps N]

Then run one agent per cell. Each agent works in its own `workspace/` (when there is
one) and writes its reply to `answer.md` beside it. Finally:

    python3 evals/grade.py <run-dir>

Why the arms are worded the way they are: the point is to measure the skill, so the
baseline arm must be prevented from reading it while still being told it is a TwinCAT
question. Telling the baseline nothing at all measures prompt luck instead.

Standard library only.
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURE = HERE / "fixture-project"

ARM_INSTRUCTION = {
    "with_skill": (
        "Read {skill} and follow it. Load whatever reference files it routes you to, and "
        "use whatever it ships in scripts/ if they apply. Then answer the request below."
    ),
    "without_skill": (
        "Answer the request below from your own knowledge. Do NOT read {skill} or anything "
        "under references/, scripts/, templates/ or examples/ — this run is the baseline it "
        "is measured against. You may read the files the request itself points you at."
    ),
}

CELL_TEMPLATE = """# {eval_name} / {arm} / {rep}

## Instruction to the agent

{instruction}

{workspace_note}
Write your complete reply to `answer.md` in this directory. That file is what gets graded.

## Request

{prompt}
"""

WORKSPACE_NOTE = (
    "The project you are being asked about is the `workspace/` directory beside this file. "
    "Work in it directly — edits you make there are part of what gets graded.\n"
)


def main():
    args = [a for a in sys.argv[1:]]
    reps = 3
    if "--reps" in args:
        i = args.index("--reps")
        reps = int(args[i + 1])
        del args[i:i + 2]
    run = Path(args[0]) if args else HERE / "runs" / "iteration-2"

    spec = json.loads((HERE / "evals.json").read_text(encoding="utf-8"))
    arms = spec.get("run", {}).get("arms", ["with_skill", "without_skill"])
    skill = "SKILL.md"

    manifest = []
    for ev in spec["evals"]:
        for arm in arms:
            for n in range(1, reps + 1):
                cell = run / ev["name"] / arm / f"rep{n}"
                cell.mkdir(parents=True, exist_ok=True)
                if ev.get("workspace"):
                    ws = cell / "workspace"
                    if ws.exists():
                        shutil.rmtree(ws)
                    shutil.copytree(FIXTURE, ws)
                    (ws / "README.md").unlink(missing_ok=True)   # not part of the project
                (cell / "PROMPT.md").write_text(CELL_TEMPLATE.format(
                    eval_name=ev["name"], arm=arm, rep=f"rep{n}",
                    instruction=ARM_INSTRUCTION[arm].format(skill=skill),
                    workspace_note=WORKSPACE_NOTE if ev.get("workspace") else "",
                    prompt=ev["prompt"],
                ), encoding="utf-8")
                manifest.append({
                    "eval": ev["name"], "arm": arm, "rep": n,
                    "scored": ev.get("scored", "discriminating"),
                    "cell": str(cell.relative_to(run)),
                    "workspace": bool(ev.get("workspace")),
                })

    (run / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    n_ws = sum(1 for m in manifest if m["workspace"])
    print(f"prepared {len(manifest)} cells under {run}")
    print(f"  {len(spec['evals'])} evals x {len(arms)} arms x {reps} reps")
    print(f"  {n_ws} of them carry a pristine copy of the fixture project")
    print(f"\nEach cell has a PROMPT.md. Run one agent per cell, from inside that cell's")
    print(f"directory, and have it write answer.md there. Then:")
    print(f"\n    python3 evals/grade.py {run}")


if __name__ == "__main__":
    main()
