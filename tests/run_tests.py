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
  * X9 catches both directions of a mixed PLCopen behaviour model, including
    pins spelled with an IEC direction prefix (ibEnable/obDone)
  * what tcpou.py scaffolds passes the reviewer tcpou.py ships beside — the two
    tools disagreed for the skill's whole life, and only a human reading both
    noticed, because nothing here ever reviewed a scaffold
  * a get/set round trip through tcpou.py is byte-exact, including on a file
    whose line endings are mixed
  * a missing path is reported rather than raising

Standard library only, like everything else here.

    python3 tests/run_tests.py
"""

import json
import re
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

# --- X9 catches both directions of a mixed behaviour model ------------------
# One fixture per branch. With only one, a typo in the other branch detects
# nothing and CI still passes on the strength of the half that works.

x9 = {f["object"] for f in review(FIXTURES / "positive") if f["rule"] == "X9"}
check("X9 fires on Enable paired with Done", "FB_EnableDone" in x9, repr(sorted(x9)))
check("X9 fires on Execute paired with Valid", "FB_ExecuteValid" in x9, repr(sorted(x9)))
check("X9 fires through an IEC direction prefix", "FB_PrefixedEnableDone" in x9,
      repr(sorted(x9)))

# --- X5 wants a guard, not merely a comparison ------------------------------
# Any '<>' or '=' against 0 counted as proof the pointer was checked, so
# 'IF p = 0 THEN Log(); END_IF; x := p^;' — which notices the null case and then
# lets it through — scanned clean. "All rules fire" cannot catch this on its own:
# X5 kept firing elsewhere in the fixture the whole time it was blind here.

x5 = {f["object"] for f in review(FIXTURES / "positive") if f["rule"] == "X5"}
check("X5 fires when a null test falls through to the dereference",
      "FB_NullFallThrough" in x5, repr(sorted(x5)))

# --- the skill's own known-good code stays clean ----------------------------

for folder in ("templates", "examples"):
    findings = review(ROOT / folder)
    high = [f for f in findings if f["severity"] == "high"]
    check(f"{folder}/ has no high-severity findings", not high,
          "; ".join(f"{f['rule']} {f['file']}:{f['line']}" for f in high))
    mixed = [f for f in findings if f["rule"] == "X9"]
    check(f"{folder}/ keeps Execute with Done and Enable with Valid", not mixed,
          "; ".join(f"{f['file']}:{f['line']}" for f in mixed))

# --- a file the reviewer cannot read must not pass ---------------------------
# A parse error used to be turned into an empty unit, so the file contributed no
# findings and the run exited 0 — the gate reporting a green check on a file it
# never analysed. Unreadable is a tool failure, so it fails regardless of
# --fail-on, which grades findings and has nothing to say about a file that
# produced none because it was never read.

with tempfile.TemporaryDirectory() as tmp:
    broken = Path(tmp) / "FB_Broken.TcPOU"
    broken.write_text('<?xml version="1.0"?>\n<TcPlcObject><POU Name="B">'
                      '<Declaration><![CDATA[FUNCTION_BLOCK B\n')
    r = subprocess.run([sys.executable, str(REVIEW), str(broken), "--json",
                        "--fail-on", "never"], capture_output=True, text=True)
    report = json.loads(r.stdout)
    check("an unparseable file fails the run even with --fail-on never",
          r.returncode != 0, f"exit {r.returncode}")
    check("an unparseable file is named in the report, not silently dropped",
          [u["file"] for u in report["files_unreadable"]] == [str(broken)],
          repr(report["files_unreadable"]))
    check("an unparseable file is not counted as scanned",
          report["files_scanned"] == 0, repr(report["files_scanned"]))

# --- the shipped TcUnit suite can reach both paths it claims to test ---------
# FB_Sequence hardcoded both step conditions to 'IF TRUE', so the timeout
# fixture always completed and the suite shipped a test that could only fail.
# Nothing here compiles ST, but the three facts the outcome turns on are all
# readable in the source.

seq = (ROOT / "templates" / "FB_Sequence.TcPOU").read_text(encoding="utf-8-sig")
suite = (ROOT / "templates" / "FB_ExampleTestSuite.TcPOU").read_text(encoding="utf-8-sig")
check("FB_Sequence's step conditions are not literals",
      not re.search(r"\bIF\s+(TRUE|FALSE)\s+THEN", seq, re.I),
      "a literal condition makes the ELSIF timeout branch unreachable")
step1 = {m.upper() for m in re.findall(r"bStep1Done\s*:=\s*(TRUE|FALSE)", suite, re.I)}
check("the suite drives its timeout fixture off the completion path",
      step1 == {"TRUE", "FALSE"},
      f"step-1 condition is always {step1} — two instances given the same inputs "
      f"can only take the same path")
ids = [re.search(r"cErrStep1Timeout\s*:\s*UDINT\s*:=\s*(16#[0-9A-Fa-f]+)", t)
       for t in (seq, suite)]
check("the suite expects the timeout id FB_Sequence actually raises",
      all(ids) and ids[0].group(1) == ids[1].group(1),
      repr([m.group(1) if m else None for m in ids]))

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

    # --- reguid regenerating nothing is a failure, not a success ------------
    # The documented workflow is copy the template, then reguid the copy. Saying
    # 'ok (0 GUIDs regenerated)' there reports the identity as refreshed when it
    # was not, leaving the copy colliding with the template on the same Id.

    noid = Path(tmp) / "NoId.TcPOU"
    noid.write_text('<?xml version="1.0" encoding="utf-8"?>\n<TcPlcObject>'
                    '<POU Name="NoId"><Declaration><![CDATA[FUNCTION_BLOCK NoId\n'
                    ']]></Declaration></POU></TcPlcObject>\n')
    before = noid.read_bytes()
    r = tcpou("reguid", str(noid))
    check("'reguid' fails when it regenerated no GUID", r.returncode == 1,
          r.stdout.decode("utf-8", "replace").strip()[:200])
    check("'reguid' leaves a file it could not stamp untouched",
          noid.read_bytes() == before)

    stamped = Path(tmp) / "Stamped.TcPOU"
    stamped.write_bytes((ROOT / "templates" / "FB_Sequence.TcPOU").read_bytes())
    r = tcpou("reguid", str(stamped))
    check("'reguid' still succeeds on a real template copy", r.returncode == 0,
          r.stdout.decode("utf-8", "replace").strip()[:200])
    check("'reguid' replaces every Id it found",
          not (set(re.findall(r'Id="\{[0-9a-fA-F-]{36}\}"',
                              stamped.read_text(encoding="utf-8-sig")))
               & set(re.findall(r'Id="\{[0-9a-fA-F-]{36}\}"',
                                (ROOT / "templates" / "FB_Sequence.TcPOU")
                                .read_text(encoding="utf-8-sig")))))

    # --- what the scaffolder emits passes the reviewer beside it ------------
    # 'new --type fb' paired bEnable with bDone for the skill's whole life: the
    # exact mix references/behaviour-model.md names as the mistake, seeded into
    # every FB an agent creates here, and with no reason for the author to doubt
    # a skeleton the skill itself produced. Reviewing a scaffold is what catches
    # the two tools drifting apart, so it is a test rather than a one-off fix.
    shapes = {
        "execute": (("bExecute", "bBusy", "bDone"), ("bEnable", "bValid")),
        "enable": (("bEnable", "bValid", "bBusy"), ("bExecute", "bDone")),
        "cyclic": ((), ("bExecute", "bEnable", "bDone", "bValid")),
    }
    for shape, (wanted, unwanted) in shapes.items():
        made = Path(tmp) / f"FB_{shape.title()}.TcPOU"
        r = tcpou("new", "--type", "fb", "--name", made.stem, "--dir", tmp, "--shape", shape)
        check(f"'new --shape {shape}' scaffolds a file",
              made.exists(), r.stderr.decode("utf-8", "replace")[:200])
        decl = tcpou("get", str(made), "--part", "decl").stdout.decode("utf-8", "replace")
        check(f"'new --shape {shape}' declares one family's pins and not the other's",
              all(p in decl for p in wanted) and not any(p in decl for p in unwanted), decl)
        bad = [f for f in review(made) if f["rule"] == "X9"]
        check(f"'new --shape {shape}' scaffolds an interface X9 accepts",
              not bad, "; ".join(f["message"] for f in bad))

    # The default is what an agent actually gets, so it is what regressed.
    default = Path(tmp) / "FB_Default.TcPOU"
    tcpou("new", "--type", "fb", "--name", default.stem, "--dir", tmp)
    decl = tcpou("get", str(default), "--part", "decl").stdout.decode("utf-8", "replace")
    check("'new --type fb' defaults to the edge-triggered shape",
          "bExecute" in decl and "bEnable" not in decl, decl)

print()
if failures:
    print(f"{len(failures)} failed")
    raise SystemExit(1)
print("all checks passed")
