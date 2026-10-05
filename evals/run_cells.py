#!/usr/bin/env python3
"""Run an eval round end to end: snapshot the skill, lay out the cells, run one
isolated headless Claude Code session per cell, grade, and report cost.

    python3 evals/run_cells.py <run-dir> --model <id> [--ref HEAD] [--reps 3]
                               [--parallel 3] [--only EVAL[,EVAL]] [--arms ARM[,ARM]]
                               [--spec evals/candidates.json] [--report-only]

<run-dir> must be outside any git repository. Running it again skips every cell that
already has a run.json, so an interrupted round resumes where it stopped; --only and
--reps narrow a first smoke test (`--reps 1 --only blocking-wait-trap`). Scouting a
candidate task is `--spec evals/candidates.json --arms without_skill --reps 1`: only a
task the model fails unaided is worth a place in the matrix.

Each cell is isolated the way it is because iteration 2 found out what happens
otherwise:

  * The environment is cleared to HOME, PATH, LANG, TERM and USER, plus a TMPDIR
    inside the cell. Agents wrote scratch files to fixed /tmp paths, which
    concurrent cells could collide on.
  * --safe-mode, --setting-sources "", --strict-mcp-config, --disable-slash-commands:
    without them the operator's own CLAUDE.md, hooks, memory, plugins and MCP
    servers reach both arms, and the run measures that setup, not the skill.
    --bare would be simpler but needs an API key, which an OAuth login lacks.
  * --no-session-persistence, or every cell leaves a transcript behind in the
    operator's Claude Code project history.
  * Only with_skill gets --add-dir, and what it gets is a snapshot of the skill at
    --ref with evals/ removed, so neither arm can read the grader.
  * --parallel defaults to 3. Four concurrent sessions once produced a transiently
    corrupted read of the shared Claude Code config file.

Standard library only, apart from the `claude` CLI itself.
"""

import argparse
import concurrent.futures
import io
import json
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CELL_TIMEOUT = 1800
ALLOWED = "Read Write Edit Glob Grep Bash"
DENIED = ("WebFetch WebSearch Agent Task PushNotification Workflow ScheduleWakeup "
          "CronCreate RemoteTrigger SendMessage DesignSync")


def inside_git(path: Path) -> bool:
    probe = path
    while not probe.exists():
        probe = probe.parent
    r = subprocess.run(["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def snapshot(ref: str, dest: Path) -> str:
    """Export the skill at `ref`, minus evals/, into dest. Returns the commit."""
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", f"{ref}^{{commit}}"],
                            capture_output=True, text=True, check=True).stdout.strip()
    stamp = dest / "SNAPSHOT.json"
    if stamp.exists():
        have = json.loads(stamp.read_text())["commit"]
        if have != commit:
            sys.exit(f"{dest} holds a snapshot of {have[:7]}, not {commit[:7]}; "
                     f"a run must not mix two versions of the skill")
        return commit
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", commit],
                         capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        keep = [m for m in t.getmembers() if m.name != "evals" and not m.name.startswith("evals/")]
        t.extractall(dest, members=keep, filter="data")
    stamp.write_text(json.dumps({"ref": ref, "commit": commit}))
    return commit


def run_cell(cell: Path, model: str, skill: Path) -> dict:
    if (cell / "run.json").exists() and (cell / "run.json").stat().st_size:
        return {"cell": cell, "skipped": True}
    tmp = cell / ".tmp"
    tmp.mkdir(exist_ok=True)
    env = {"HOME": os.environ["HOME"], "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
           "TERM": "dumb", "USER": os.environ.get("USER", ""), "TMPDIR": str(tmp)}
    cmd = ["claude", "-p", (cell / "PROMPT.md").read_text(encoding="utf-8"),
           "--model", model, "--safe-mode", "--setting-sources", "",
           "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
           "--permission-mode", "dontAsk", "--allowedTools", ALLOWED,
           "--disallowedTools", DENIED, "--output-format", "stream-json", "--verbose"]
    if cell.parent.name == "with_skill":
        cmd += ["--add-dir", str(skill)]
    start = time.time()
    with open(cell / "run.jsonl", "wb") as out, open(cell / "run.err", "wb") as err:
        try:
            rc = subprocess.run(cmd, cwd=cell, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, timeout=CELL_TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 124
    result = [l for l in (cell / "run.jsonl").read_text(errors="replace").splitlines()
              if '"type":"result"' in l]
    (cell / "run.json").write_text(result[-1] if result else "")
    wall = round(time.time() - start)
    (cell / "run.meta.json").write_text(json.dumps({"rc": rc, "wall_s": wall, "model": model}))
    return {"cell": cell, "rc": rc, "wall": wall}


def tool_calls(jsonl: Path) -> list[tuple[str, dict, str]]:
    calls = []
    for line in jsonl.read_text(errors="replace").splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") == "assistant":
            for b in m.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    calls.append((b["name"], b.get("input", {}), json.dumps(b.get("input", {}))))
    return calls


def inside(cell: Path, path: str) -> bool:
    target = (cell / path).resolve()          # an absolute path replaces cell / ...
    return target == cell or cell in target.parents


def report(run: Path, skill: Path) -> str:
    """Per-arm cost, plus an audit of what each cell actually touched."""
    lines, rows = [], []
    for f in sorted(run.glob("*/*/rep*/run.json")):
        cell = f.parent
        ev, arm, rep = cell.parts[-3], cell.parts[-2], cell.parts[-1]
        try:
            d = json.loads(f.read_text())
        except ValueError:
            lines.append(f"{ev}/{arm}/{rep}: no result recorded (crashed or timed out)")
            continue
        u = d.get("usage", {})
        tok = sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                        "cache_read_input_tokens", "output_tokens"))
        calls = tool_calls(cell / "run.jsonl")
        flags = []
        if arm == "without_skill" and any(str(skill) in c[2] for c in calls):
            flags.append("BASELINE-READ-SKILL")
        if arm == "with_skill" and not any("SKILL.md" in c[2] for c in calls):
            flags.append("SKILL-NOT-READ")
        if any(c[0] in ("Write", "Edit") and not inside(cell, c[1].get("file_path", ""))
               for c in calls):
            flags.append("WROTE-OUTSIDE-CELL")
        if "corrupted" in (cell / "run.err").read_text(errors="replace"):
            flags.append("CONFIG-RACE")
        rows.append({"arm": arm, "ev": ev, "tok": tok, "cost": d.get("total_cost_usd", 0),
                     "dur": d.get("duration_ms", 0) / 1000})
        lines.append(f"{ev:24s} {arm:13s} {rep} tok={tok:>9,} ${d.get('total_cost_usd', 0):.2f} "
                     f"{d.get('duration_ms', 0) / 1000:5.0f}s calls={len(calls):3d} "
                     f"{' '.join('!!' + x for x in flags)}")
    lines.append("")
    for arm in ("with_skill", "without_skill"):
        a = [r for r in rows if r["arm"] == arm]
        if a:
            lines.append(f"{arm:13s} n={len(a)} mean tok={statistics.mean(r['tok'] for r in a):,.0f} "
                         f"mean {statistics.mean(r['dur'] for r in a):.0f}s "
                         f"mean ${statistics.mean(r['cost'] for r in a):.2f} "
                         f"total ${sum(r['cost'] for r in a):.2f} "
                         f"total tok={sum(r['tok'] for r in a):,}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run_dir", type=Path)
    p.add_argument("--model", required=True, help="pinned for both arms and recorded per cell")
    p.add_argument("--ref", default="HEAD", help="git ref of the skill to evaluate")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--only", default="", help="comma-separated eval names")
    p.add_argument("--arms", default="", help="comma-separated arms, e.g. without_skill")
    p.add_argument("--spec", type=Path, help="eval spec instead of evals/evals.json")
    p.add_argument("--report-only", action="store_true")
    a = p.parse_args()

    run = a.run_dir.resolve()
    if inside_git(run):
        sys.exit(f"{run} is inside a git repository; put the run outside one, or the "
                 f"cells can pick up that repository's CLAUDE.md")
    if not a.report_only and not shutil.which("claude"):
        sys.exit("the claude CLI is not on PATH")
    run.mkdir(parents=True, exist_ok=True)
    skill = run / "_skill"
    commit = snapshot(a.ref, skill)

    # Laid out once. prepare_run.py recreates each workspace from the pristine
    # fixture, so running it again would wipe what finished cells left behind.
    if not (run / "MANIFEST.json").exists():
        subprocess.run([sys.executable, str(HERE / "prepare_run.py"), str(run),
                        "--reps", str(a.reps), "--skill", str(skill / "SKILL.md")]
                       + (["--spec", str(a.spec.resolve())] if a.spec else []), check=True)
    manifest = json.loads((run / "MANIFEST.json").read_text())
    only = {x for x in a.only.split(",") if x}
    arms = {x for x in a.arms.split(",") if x}
    cells = [run / m["cell"] for m in manifest
             if (not only or m["eval"] in only) and (not arms or m["arm"] in arms)]

    if not a.report_only:
        print(f"skill {commit[:7]} ({a.ref}), model {a.model}, {len(cells)} cells, "
              f"{a.parallel} at a time")
        with concurrent.futures.ThreadPoolExecutor(a.parallel) as pool:
            for i, r in enumerate(pool.map(lambda c: run_cell(c, a.model, skill), cells), 1):
                rel = r["cell"].relative_to(run)
                print(f"[{i}/{len(cells)}] {rel} " +
                      ("skipped, already run" if r.get("skipped") else f"rc={r['rc']} {r['wall']}s"),
                      flush=True)

    subprocess.run([sys.executable, str(HERE / "grade.py"), str(run)])
    text = report(run, skill)
    (run / "REPORT.txt").write_text(text + "\n")
    print("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
