#!/usr/bin/env python3
"""Detection tests for scripts/st_review.py and scripts/tcpou.py.

CI already proves the reviewer stays quiet on known-good code. That can never
catch a rule which has silently stopped detecting anything — which is exactly how
CP8 came to miss `bAtTarget := (fA = fB);`, the assignment form of the single
defect this skill leads with. This is the other half of the gate:

  * every rule in RULES fires at least once on tests/fixtures/positive/
  * nothing fires on tests/fixtures/negative/, which collects the shapes that
    were false positives until they were fixed
  * X6 separates an FB input from a METHOD parameter by severity
  * a get/set round trip through tcpou.py is byte-exact, including on a file
    whose line endings are mixed
  * a missing path is reported rather than raising

Standard library only, like everything else here.

    python3 tests/run_tests.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REVIEW = ROOT / "scripts" / "st_review.py"
TCPOU = ROOT / "scripts" / "tcpou.py"
FIXTURES = HERE / "fixtures"

sys.path.insert(0, str(ROOT / "scripts"))
import st_review  # noqa: E402 — imported for RULES so the expected set cannot drift

failures = []


def check(label, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        if detail:
            print(f"        {detail}")
        failures.append(label)


def review(target, *flags):
    out = subprocess.run(
        [sys.executable, str(REVIEW), str(target), "--json", *flags],
        capture_output=True, text=True,
    )
    if not out.stdout.strip():
        raise SystemExit(f"reviewer produced no output for {target}:\n{out.stderr}")
    return json.loads(out.stdout)["findings"]


def tcpou(*args, stdin=None):
    return subprocess.run([sys.executable, str(TCPOU), *args],
                          input=stdin, capture_output=True)


# --- every rule still detects its defect ------------------------------------

fired = {f["rule"] for f in review(FIXTURES / "positive", "--pedantic")}
missing = sorted(set(st_review.RULES) - fired)
check(f"all {len(st_review.RULES)} rules fire on the positive fixtures",
      not missing, "never fired: " + ", ".join(missing))

# --- and stays silent on the shapes that were false positives ---------------

noise = review(FIXTURES / "negative")
check("no findings on the negative fixtures", not noise,
      "; ".join(f"{f['rule']} {f['object']}:{f['line']} {f['message'][:70]}" for f in noise))

# --- X6 ranks an unwired FB input above a bound method parameter ------------

x6 = {f["object"]: f["severity"] for f in review(FIXTURES / "positive") if f["rule"] == "X6"}
check("X6 is medium on an FB input", x6.get("FB_AllRules") == "medium", repr(x6))
check("X6 is low on a METHOD parameter", x6.get("HandleValue") == "low", repr(x6))

# --- the skill's own known-good code stays clean ----------------------------

for folder in ("templates", "examples"):
    high = [f for f in review(ROOT / folder) if f["severity"] == "high"]
    check(f"{folder}/ has no high-severity findings", not high,
          "; ".join(f"{f['rule']} {f['file']}:{f['line']}" for f in high))

# --- tcpou.py round trips the bytes it was not asked to change --------------

src = (ROOT / "examples" / "packml-vffs" / "FB_EquipmentModuleTemplate.TcPOU").read_bytes()
lf = (src[len(b"\xef\xbb\xbf"):] if src.startswith(b"\xef\xbb\xbf") else src).replace(b"\r\n", b"\n")
variants = {
    "BOM + CRLF": b"\xef\xbb\xbf" + lf.replace(b"\n", b"\r\n"),
    "BOM + LF": b"\xef\xbb\xbf" + lf,
    "no BOM + LF": lf,
    "mixed endings": lf.replace(b"\n", b"\r\n", 1),
}
with tempfile.TemporaryDirectory() as tmp:
    for label, data in variants.items():
        target = Path(tmp) / "roundtrip.TcPOU"
        target.write_bytes(data)
        for part in ("impl", "Initialize:impl", "Initialize:decl"):
            got = tcpou("get", str(target), "--part", part)
            tcpou("set", str(target), "--part", part, stdin=got.stdout)
        check(f"get/set is byte-exact: {label}", target.read_bytes() == data,
              "the file changed outside the part that was edited")

    # --- a missing path is an error message, not a stack trace --------------

    absent = str(Path(tmp) / "absent.TcPOU")
    for cmd in (["check", absent], ["show", absent], ["reguid", absent],
                ["get", absent, "--part", "impl"], ["register", absent, absent]):
        r = tcpou(*cmd)
        err = r.stderr.decode("utf-8", "replace")
        check(f"'{cmd[0]}' reports a missing path cleanly",
              r.returncode == 1 and "Traceback" not in err, err.strip()[:200])

print()
if failures:
    print(f"{len(failures)} failed")
    raise SystemExit(1)
print("all checks passed")
