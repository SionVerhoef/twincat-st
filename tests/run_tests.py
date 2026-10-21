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
  * a variable is the same variable under any spelling of its name, and however
    its declaration is aligned — ST identifiers are case-insensitive
  * a text source holding several POUs is parsed as several POUs — merging
    them hid every body but the last and crossed their variable scopes
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

# Count the shapes, do not just look for the object: the first fix here searched
# a window for '<> 0' and so cured 'IF p = 0 THEN ... END_IF; p^' while leaving
# its mirror — 'IF p <> 0 THEN ... END_IF; p^' — and the ELSE branch of a correct
# test still reporting clean. An object-name assertion stays green on one of three.
x5_lines = sorted(f["line"] for f in review(FIXTURES / "positive")
                  if f["rule"] == "X5" and f["object"] == "FB_NullFallThrough")
check("X5 fires on all three fall-through shapes, not only the '= 0' one",
      len(x5_lines) == 3, f"fired at lines {x5_lines}, expected 3")

# --- CP8 tells change detection from arrival ---------------------------------
# A field test on a real project found 'fTarget := fSetpoint;' followed by
# 'bChanged := (fTarget <> fSetpoint)' reported high. That compare asks whether
# the setpoint moved since the latch, where exact is right; the negative fixture
# holds it. Skipping it must not also silence the measured position compared
# with that same target, which was the other high finding there and a real one.

cp8 = [f["source"] for f in review(FIXTURES / "positive")
       if f["rule"] == "CP8" and f["object"] == "FB_LatchedCompare"]
check("CP8 fires on a measured value against a latched target, not on the latch check",
      cp8 == ["bInPosition := (fActPos = fTarget);"], repr(cp8))

# --- X11 reads Execute in both places it can be written ---------------------
# The field test's B2b: the prompt's own move passed Execute in the call, the
# agent's second one assigned the member before calling. One form alone would let
# the other through. FB_StepExecute holds the edge-correct shapes on the other side.

x11 = sorted(f["line"] for f in review(FIXTURES / "positive")
             if f["rule"] == "X11" and f["object"] == "FB_LevelExecute")
check("X11 fires on a level Execute in the call and on the member", x11 == [18, 19],
      repr(x11))

# --- a CFC body's operands are uses, and only its operands ------------------
# CP24 read only <Implementation><ST>, so every variable wired in a CFC network
# came back unused: 124 findings in 19 POUs on a real project. The negative
# fixture FB_CfcBody holds that side. Skipping graphical POUs outright would be
# the lazy fix, so a variable the network never names must still be reported.

cfc = (FIXTURES / "negative" / "FB_CfcBody.TcPOU").read_text(encoding="utf-8-sig")
with tempfile.TemporaryDirectory() as tmp:
    dead = Path(tmp) / "FB_CfcDead.TcPOU"
    dead.write_text(cfc.replace("    stCfg    : ST_Cfg;",
                                "    stCfg    : ST_Cfg;\n    nSpare   : INT;"), encoding="utf-8")
    unused = [f["source"] for f in review(dead) if f["rule"] == "CP24"]
    check("CP24 still reports a variable a CFC network never names",
          unused == ["nSpare : INT"], repr(unused))

# --- code inside an <Action> is code ----------------------------------------
# parse_xml walked every container except Action, which tcpou.py has always
# recognised. The gap cut both ways: defects in the action went unreported, and
# the declarations the action used came back as CP24 unused, because from the
# reviewer's side nothing referenced them.

positive = review(FIXTURES / "positive")
act = [f for f in positive if f["object"] == "Act_Compare"]
check("a defect inside an <Action> is reported, and against the action",
      any(f["rule"] == "CP8" for f in act), repr([(f["rule"], f["object"]) for f in act]))
check("variables an <Action> uses are not called unused",
      not [f for f in positive
           if f["rule"] == "CP24" and f["object"] == "FB_ActionDefect"],
      "the action's code is invisible again")

# --- X3 and X7 look at structure, not at a word anywhere in the file --------
# X3 accepted a nested IF's ELSE as the CASE's fallback, and X7 accepted any
# identifier containing Error/Fault/Alarm/Abort — which a bError output supplies
# in nearly every FB. Both rules stayed quiet on exactly what they exist to find.
# The negative fixtures hold the other side: a numerically-labelled machine whose
# step 99 raises the fault flag has an error state, and must not be reported.

x3 = {f["object"] for f in positive if f["rule"] == "X3"}
check("X3 fires when the only ELSE belongs to a nested IF",
      "FB_NestedElse" in x3, repr(sorted(x3)))
x7 = {f["object"] for f in positive if f["rule"] == "X7"}
check("X7 fires even though the FB declares a bError output",
      "FB_StateNoError" in x7, repr(sorted(x7)))

# Both rules judge a state variable across every CASE over it, so a secondary
# CASE that only picks a value per step (negative fixtures x7_secondary_case, FB_SecondaryCase) is
# covered by the main one. Take the main one's ELSE and error step away and the
# variable must be reported once each, at its first CASE — not once per CASE, and
# not zero times because one CASE stood in for another.

sec = (FIXTURES / "negative" / "FB_SecondaryCase.st").read_text(encoding="utf-8")
bare = re.sub(r"    E_Step\.DeviceError:.*?END_IF\nELSE\n.*?\n", "", sec, flags=re.S)
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "secondary_bare.st"
    p.write_text(bare, encoding="utf-8")
    got = sorted((f["rule"], f["line"]) for f in review(p) if f["rule"] in ("X3", "X7"))
    check("X3 and X7 report a state variable once, at its first CASE",
          got == [("X3", 16), ("X7", 16)], repr(got))

# --- X2 keys on the type, not on a name that sounds like a timeout ----------
# 'udiTimeOut' is PLCopen's UDINT millisecond pin, so a plain number is correct
# there and T#500MS would be the type error — yet X2 reported it high. 'PT' is
# TIME on every standard timer and must still be caught.

x2 = {f["object"] for f in positive if f["rule"] == "X2"}
check("X2 still fires on a bare number given to PT",
      "FB_AllRules" in x2, repr(sorted(x2)))

# --- both rules scope to what they are actually judging ----------------------
# X7 pooled every label in the file, so an error label in an unrelated CASE — or
# in a method further down — stood in for a machine that had none. X2 compared
# identifiers case-sensitively, which ST is not: a TIME variable assigned under a
# different spelling of its own name went unchecked.

check("X7 judges each state machine on its own body",
      "FB_ScopeAndCase" in x7,
      "an unrelated CASE's error label is covering for a machine without one")
check("X2 matches a TIME variable whatever case it is spelled in",
      "FB_ScopeAndCase" in x2, repr(sorted(x2)))

# --- a variable is the same variable under any spelling or alignment ---------
# CP24 stripped a declaration by the literal 'name :', so a column-aligned one
# stayed in the text and the variable looked referenced. And every rule keyed on
# a declared name compared it as written, which ST does not: a use under another
# spelling was invisible to CP8, X5, CP20 and X6, and called CP24 'unused'. The
# negative fixture FB_CaseFoldedClean holds the false-positive half.

cased = {(f["rule"], f["source"].split(":")[0].strip())
         for f in positive if f["object"] == "FB_AlignedAndCased"}
for rule, name, what in [
    ("CP24", "nUnusedAligned", "an unused variable whose declaration is column-aligned"),
    ("CP8", "IF factual = nCount THEN", "a REAL compared under another spelling"),
    ("X5", "pdata^", "a pointer dereferenced under another spelling"),
    ("E3", "IF pdata > nCount", "a pointer ordered under another spelling"),
    ("CP20", "fbDelay(IN", "an FB instance called twice under two spellings"),
    ("X6", "refValue", "a reference used only under another spelling"),
]:
    hit = any(r == rule and t.startswith(name) for r, t in cased)
    check(f"{rule} fires on {what}", hit, repr(sorted(cased)))

# --- a finding names the line and the unit it is actually about --------------
# X10: prose left in a VAR block by a comment that lost its '//' compiled nowhere
# and was reported nowhere. X7 found a state machine in a METHOD but named the POU
# body, because it searched every unit's code joined together. The negative
# fixture FB_DeclarationShapes holds the valid shapes X10 must not flag, and the
# non-BOOL 'iEnable' that X9 must not read as a PLCopen pin.

stray = [f for f in positive if f["rule"] == "X10"]
check("X10 fires on the prose line, and only there",
      [(f["object"], f["source"][:20]) for f in stray]
      == [("FB_StrayAndMethodMachine", "which is advanced on")], repr(stray))
check("X7 names the METHOD holding the state machine, not the POU around it",
      {f["object"] for f in positive if f["rule"] == "X7"
       and f["file"].endswith("FB_StrayAndMethodMachine.TcPOU")} == {"Run"},
      repr([f for f in positive if f["rule"] == "X7"]))

# --- a text source holding several POUs is not one POU ----------------------
# parse_text used to split the whole file at its last END_VAR, which assumes one
# POU per file. TwinCAT writes one POU per file so no .TcPOU ever showed it, but a
# CODESYS text export does not, and the failure was silent in both directions: the
# earlier bodies ended up inside the merged declaration and were never scanned, and
# the merged variable scope let one block's trigger pair with another's completion.
# Both halves are asserted, because fixing only the split turns the silent miss into
# a false positive instead.

MULTI_POU = """FUNCTION_BLOCK FB_First
VAR_INPUT
    bEnable : BOOL;
END_VAR
VAR
    fA : LREAL;
    bEq : BOOL;
END_VAR
bEq := bEnable AND (fA = 1.0);

FUNCTION_BLOCK FB_Second
VAR_OUTPUT
    bDone : BOOL;
END_VAR
VAR
    fB : LREAL;
END_VAR
bDone := (fB = 2.0);
"""

with tempfile.TemporaryDirectory() as tmp:
    multi = Path(tmp) / 'two_pous.st'
    multi.write_text(MULTI_POU, encoding='utf-8')
    findings = review(multi)
    cp8 = {f['object'] for f in findings if f['rule'] == 'CP8'}
    check("every POU's body in a text source is scanned",
          cp8 == {'FB_First', 'FB_Second'}, repr(sorted(cp8)))
    crossed = [f for f in findings if f['rule'] == 'X9']
    check('X9 does not pair pins across POU boundaries', not crossed,
          '; '.join(f"{f['object']}:{f['line']} {f['message'][:60]}" for f in crossed))


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
    # Exactly 2, not merely nonzero: 2 is the documented contract and is what
    # separates "could not check" from "checked and found something" (1). A
    # regression to 1 would keep a `!= 0` assertion green.
    check("an unparseable file exits 2 even with --fail-on never",
          r.returncode == 2, f"exit {r.returncode}")
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
# The template shipped its step timer called from inside the Step1 and Step2
# branches — the shape references/cyclic-execution-rules.md Rule 5 prints under a
# WRONG comment, in the skill's own flagship template. Rule 5 also calls sharing
# one timer instance across states a bug. No rule in st_review.py looks for this,
# so this check is the only thing keeping the template off the shape its own
# reference forbids.
seq_body = seq.split("<Implementation>")[1].split("</Implementation>")[0]
timer_calls = list(re.finditer(r"\bfbStepTimer\s*\(", seq_body))
case_at = seq_body.find("CASE ")
check("FB_Sequence services its step timer from exactly one call site",
      len(timer_calls) == 1, f"{len(timer_calls)} call sites")
check("FB_Sequence services its step timer above the CASE, not inside a branch",
      bool(timer_calls) and case_at > 0 and timer_calls[0].start() < case_at,
      "a timer called inside the branch that reads it stops being serviced "
      "the moment the state machine leaves that branch")

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

    # --- tcpou.py reads and writes UTF-8 whatever the locale says ------------
    # On Windows the default text encoding is cp1252. 'set --from-file' read a
    # UTF-8 part file through it, so every '²' in a unit comment came back as
    # 'Â²' after a get/set that edited nothing, and 'get' aborted on a character
    # cp1252 cannot encode. The env below forces that locale; on Linux, where
    # cp1252 is not available as a locale, LC_ALL=C makes it ASCII instead, which
    # fails the unfixed tool just as surely.
    import os
    legacy = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0",
              "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"}
    units = Path(tmp) / "FB_Units.TcPOU"
    units.write_bytes(
        b"\xef\xbb\xbf" + '<?xml version="1.0" encoding="utf-8"?>\r\n<TcPlcObject>\r\n'
        '  <POU Name="FB_Units" Id="{00000000-0000-0000-0000-000000000001}">\r\n'
        '    <Declaration><![CDATA[FUNCTION_BLOCK FB_Units\r\nVAR\r\n'
        '    fAccel : LREAL;    // [mm/s²]\r\n    fVolume : LREAL;   // [m³] ── buffer\r\n'
        'END_VAR\r\n]]></Declaration>\r\n  </POU>\r\n</TcPlcObject>\r\n'.encode("utf-8"))
    original = units.read_bytes()
    got = subprocess.run([sys.executable, str(TCPOU), "get", str(units), "--part", "decl"],
                         capture_output=True, env=legacy)
    check("'get' writes UTF-8 under a legacy locale",
          got.returncode == 0 and "[mm/s²]".encode("utf-8") in got.stdout
          and "──".encode("utf-8") in got.stdout,
          got.stderr.decode("utf-8", "replace").strip()[-200:])
    # The part file is what 'get' should have written, so these checks stand on
    # their own when 'get' is the half that broke. Labels stay ASCII: this runner
    # prints them to a cp1252 console on Windows.
    decl = original.decode("utf-8-sig").split("<![CDATA[")[1].split("]]>")[0]
    part = Path(tmp) / "units_decl.st"
    part.write_bytes(decl.replace("\r\n", "\n").encode("utf-8"))
    for how, args, feed in (("--from-file", ["--from-file", str(part)], None),
                            ("stdin", [], part.read_bytes())):
        r = subprocess.run([sys.executable, str(TCPOU), "set", str(units), "--part", "decl",
                            *args], input=feed, capture_output=True, env=legacy)
        check(f"set via {how} keeps unit comments byte-exact under a legacy locale",
              r.returncode == 0 and units.read_bytes() == original,
              r.stderr.decode("utf-8", "replace").strip()[-200:]
              or repr(units.read_bytes().decode("utf-8", "replace")[150:260]))
        units.write_bytes(original)

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

    # --- add-method / add-property: the A3 round trip, without a hand edit ----
    # The field test's A3 says new -> register -> set one method -> reguid ->
    # check, but nothing scaffolded a method: it was pasted in by hand from the
    # template's XML. These are the steps an agent would run, end to end.
    rt = Path(tmp) / "FB_RoundTrip.TcPOU"
    tcpou("new", "--type", "fb", "--name", rt.stem, "--dir", tmp)
    before = rt.read_bytes()
    r1 = tcpou("add-method", str(rt), "--name", "M_Reset", "--returns", "BOOL",
               "--access", "PRIVATE")
    r2 = tcpou("add-property", str(rt), "--name", "Position", "--type", "LREAL", "--no-set")
    tcpou("set", str(rt), "--part", "M_Reset:impl", stdin=b"bDone := FALSE;\nM_Reset := TRUE;\n")
    after = rt.read_bytes()
    keys = set(re.findall(r"^\s*(\S+)\s", tcpou("show", str(rt)).stdout.decode(), re.M)[1:])
    check("add-method and add-property create the parts set and get address",
          r1.returncode == 0 and r2.returncode == 0
          and {"M_Reset:decl", "M_Reset:impl", "Position:decl", "Position.Get:impl"} <= keys
          and "Position.Set:impl" not in keys, repr(sorted(keys)))
    head, tail = before.split(b"  </POU>")
    check("add-method inserts before </POU> and changes nothing else",
          after.startswith(head) and after.endswith(b"  </POU>" + tail), "")
    body = after[3:]
    check("add-method keeps the BOM and writes CRLF only",
          after.startswith(b"\xef\xbb\xbf") and body.count(b"\n") == body.count(b"\r\n"), "")
    ids = re.findall(rb'Id="(\{[0-9a-f-]{36}\})"', after)
    check("every added object carries its own fresh Id", len(ids) == len(set(ids)) == 4,
          repr(ids))
    check("a scaffold with a method still passes check",
          tcpou("check", str(rt)).returncode == 0
          and tcpou("reguid", str(rt)).returncode == 0
          and tcpou("check", str(rt)).returncode == 0)
    check("the reviewer reads the added method without a stray-line finding",
          not [f for f in review(rt) if f["rule"] == "X10"])
    check("add-method refuses a name that already exists, in any case",
          tcpou("add-method", str(rt), "--name", "m_reset").returncode == 1)

    itf = Path(tmp) / "I_Thing.TcIO"
    itf.write_bytes((ROOT / "examples" / "design-patterns-state" / "I_State.TcIO").read_bytes())
    tcpou("add-method", str(itf), "--name", "Probe", "--returns", "BOOL")
    member = itf.read_text(encoding="utf-8-sig").split('Name="Probe"')[1].split("</Method>")[0]
    check("an interface method gets no <Implementation>", "<Implementation>" not in member,
          member)
    check("an interface member refuses an access modifier",
          tcpou("add-method", str(itf), "--name", "P2", "--access", "PRIVATE").returncode == 1)

print()
if failures:
    print(f"{len(failures)} failed")
    raise SystemExit(1)
print("all checks passed")
