#!/usr/bin/env python3
"""Static review for IEC 61131-3 Structured Text (CODESYS V3 family / TwinCAT 3).

Findings are keyed to a rule id so a review can cite one:

  CP*/N*/C*/L*/E*   PLCopen Coding Guidelines v1.0 rule ids, with PLCopen's own
                    Importance rating carried through as the severity.
  X*                This skill's own ids, where that catalogue is silent: the
                    failure modes specific to a scanned real-time task, plus X9 for
                    the PLCopen *behaviour model* contract, which is standardised in
                    a different document. See references/cyclic-execution-rules.md
                    and references/behaviour-model.md.

Reads .TcPOU / .TcDUT / .TcGVL / .TcIO (XML, code in CDATA) and plain .st/.txt.
For XML it walks *every* Declaration/Implementation pair — POU body, methods,
property getters and setters. A top-level-only parse silently misses about 84%
of the code in OOP projects, which is the whole reason this script exists.

    python3 st_review.py <file-or-dir>...
    python3 st_review.py src/ --json
    python3 st_review.py src/ --min-severity high      # CI gate
    python3 st_review.py src/ --rules X1,X2,CP8        # only these

Exit status is 1 when a finding at or above --fail-on (default: high) is
reported, so it can gate a pipeline. Nothing here compiles the code: a clean
run means "no known defect pattern matched", not "this builds".

Suppress a finding you have judged acceptable by putting a reason on the line
or the line above:

    WHILE NOT fbBus.bDone DO   // lint:allow X1 bounded by fbBus watchdog

An unexplained suppression is itself reported (X0), because a bare silencer is
indistinguishable from an unreviewed defect.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

XML_SUFFIXES = {".tcpou", ".tcdut", ".tcgvl", ".tcio"}
TEXT_SUFFIXES = {".st", ".txt", ".iecst"}

SEVERITIES = ("high", "medium", "low")

# rule id -> (severity, one-line description). Severity for PLCopen ids is that
# document's own Importance field, so a report can be ranked the way the
# standard ranks it rather than the way this script feels about it.
RULES: dict[str, tuple[str, str]] = {
    "X0": ("low", "lint:allow suppression without a stated reason"),
    "X1": ("high", "unbounded WHILE/REPEAT — blocks the scan; use a state machine"),
    "X2": ("high", "timer preset assigned a bare number instead of a TIME literal"),
    "X3": ("medium", "CASE without ELSE — corrupted or new state falls through silently"),
    "X4": ("medium", "division by a variable with no zero guard"),
    "X5": ("high", "pointer dereferenced without a NULL check"),
    # Reported low when the reference is a METHOD parameter: a method call site must
    # supply every input, so that reference is always bound. Still reported, because
    # a caller can pass its own unassigned reference straight through.
    "X6": ("medium", "REFERENCE TO used without __ISVALIDREF anywhere in the POU "
                     "(low for a METHOD parameter, which the call site always binds)"),
    "X7": ("medium", "state machine has no error/fault state"),
    "X8": ("medium", "FB_init does real work without an online-change (bInCopyCode) guard"),
    "X9": ("medium", "FB mixes the two PLCopen behaviour models — Enable with Done, "
                     "or Execute with Valid"),
    "CP8": ("high", "equality/inequality comparison on REAL/LREAL"),
    "CP13": ("high", "POU calls itself — recursion is not allowed"),
    "CP14": ("high", "RETURN before the end of the POU — single point of exit"),
    # PLCopen rates CP20 Medium. Held at low here because counting call sites in the
    # text cannot prove two of them are reachable in the same scan — calls sitting in
    # mutually exclusive CASE branches are correct and common. Worth a look, not an alarm.
    "CP20": ("low", "function block instance called from more than one site in one body"),
    "CP23": ("medium", "POU has more than 10 input/output/in-out parameters"),
    "CP24": ("medium", "variable declared but never used"),
    "CP28": ("high", "equality/inequality comparison on TIME"),
    "E1": ("high", "dynamic allocation (__NEW/__DELETE) outside FB_init/FB_exit"),
    "E3": ("high", "ordering comparison (< > <= >=) applied to a pointer"),
    "L11": ("medium", "line longer than 80 characters"),
}

# Severities above are PLCopen's own Importance field, so a report ranks the way
# the standard ranks it. One deliberate exception, marked at its entry: CP20 is
# held below PLCopen's Medium because counting call sites in text cannot prove two
# are reachable in the same scan.
#
# These two are real rules that nonetheless fire hundreds of times on well-regarded
# reference code — the early-RETURN guard clause is a widespread, defensible idiom,
# and line length is a house matter. On by default they bury the defect findings,
# and a report nobody reads is worse than no report. Opt in with --pedantic.
PEDANTIC = {"L11", "CP14"}

MAX_LINE = 80          # L11
MAX_POU_PINS = 10      # CP23, PLCopen's suggested limit
REAL_TYPES = {"REAL", "LREAL"}
TIME_TYPES = {"TIME", "LTIME"}

# Parameters the runtime imposes on the implicit-initialisation methods. They are
# part of a fixed signature, so an implementation that ignores one has not left a
# stray variable lying around and must not be reported as if it had.
FIXED_SIGNATURE_PARAMS = {
    "FB_INIT": {"bInitRetains", "bInCopyCode"},
    "FB_EXIT": {"bInCopyCode"},
    "FB_REINIT": set(),
}

VAR_SECTION = re.compile(
    r"^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_STAT|VAR_INST|VAR_GLOBAL|VAR_EXTERNAL|VAR)"
    r"(\s+(?:CONSTANT|RETAIN|PERSISTENT|PUBLIC|PRIVATE|PROTECTED|INTERNAL))*\s*$",
    re.I,
)
END_VAR = re.compile(r"^\s*END_VAR\s*$", re.I)
DECL_LINE = re.compile(r"^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*:\s*([^:=;]+?)\s*(?::=.*)?;", re.S)
POU_HEADER = re.compile(
    r"^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM|METHOD|INTERFACE|PROPERTY)\s+"
    r"(?:(?:PUBLIC|PRIVATE|PROTECTED|INTERNAL|ABSTRACT|FINAL|OVERRIDE)\s+)*"
    r"([A-Za-z_]\w*)",
    re.I,
)
SUPPRESS = re.compile(r"//\s*lint:allow\s+([A-Za-z0-9_,]+)\s*(.*)$", re.I)

# The command pins of the two PLCopen behaviour models (X9). Matched whole, allowing an
# optional IEC direction letter ahead of the conventional type letter, because half the
# Beckhoff codebases in the field spell their pins ibEnable and obDone. Without that
# prefix the rule reads as clean on code it has simply failed to look at: on one real
# 1374-file project it reported nothing while 108 function blocks carried an Enable pin.
# Anchoring is what keeps the rule honest — obPurgeCycleDone is the named completion of one
# specific operation, not a PLCopen completion pin, and a substring match cannot tell the
# two apart. A house name like bExecuteMove is left alone for the same reason: guessing
# wrong makes the rule argue with code that is right.
PIN_EXECUTE = re.compile(r"^[ioq]?[bx]?Execute$", re.I)
PIN_ENABLE = re.compile(r"^[ioq]?[bx]?Enable$", re.I)
PIN_DONE = re.compile(r"^[ioq]?[bx]?Done$", re.I)
PIN_VALID = re.compile(r"^[ioq]?[bx]?Valid$", re.I)

# ST keywords that must never be mistaken for an identifier being called.
KEYWORDS = {
    "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF", "END_CASE", "FOR", "TO",
    "BY", "DO", "END_FOR", "WHILE", "END_WHILE", "REPEAT", "UNTIL", "END_REPEAT",
    "EXIT", "CONTINUE", "RETURN", "VAR", "END_VAR", "TRUE", "FALSE", "AND", "OR",
    "XOR", "NOT", "MOD", "SUPER", "THIS", "SIZEOF", "ADR", "REF", "SEL", "MUX",
    "MIN", "MAX", "LIMIT", "ABS", "SQRT", "TRUNC", "ROUND",
}


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    obj: str
    line: int
    text: str
    message: str

    def as_dict(self) -> dict:
        return {
            "rule": self.rule, "severity": self.severity, "file": self.file,
            "object": self.obj, "line": self.line, "source": self.text.strip(),
            "message": self.message,
        }


@dataclass
class Unit:
    """One Declaration/Implementation pair: a POU body, method, getter or setter."""
    name: str
    kind: str
    decl: str
    impl: str
    decl_line: int = 1   # absolute first line of the declaration inside the file
    impl_line: int = 1


@dataclass
class Variable:
    name: str
    type: str
    section: str
    line: int
    unit: str


@dataclass
class SourceFile:
    path: Path
    units: list[Unit] = field(default_factory=list)
    raw: str = ""


# --------------------------------------------------------------------------- parse

def strip_noise(code: str) -> str:
    """Blank out comments and string literals, preserving line and column layout.

    Every lexical check below runs on this. Without it, the word 'WHILE' in a
    comment and a divisor inside a string both produce phantom findings, and a
    linter that cries wolf stops being read.
    """
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        two = code[i:i + 2]
        if two == "//":
            j = code.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif two in ("(*", "/*"):
            close = "*)" if two == "(*" else "*/"
            j = code.find(close, i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif code[i] in "'\"":
            q = code[i]
            j = i + 1
            while j < n and code[j] != q:
                j += 2 if code[j] == "$" else 1     # $' is the ST escape
            j = min(j + 1, n)
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    cleaned = "".join(out)
    # 'THIS^.' is the dominant way to touch an own member (3658 occurrences across
    # the reference corpus). Blanking it — same width, so line and column stay put
    # — lets every identifier check below treat 'THIS^.refSocket' as a plain use of
    # 'refSocket'. Without this, unused-variable and call-count checks are wrong in
    # exactly the object-oriented code they matter most for.
    return re.sub(r"THIS\s*\^\s*\.", lambda m: " " * len(m.group(0)), cleaned, flags=re.I)


def line_of(raw: str, needle: str) -> int:
    """Absolute 1-based line where a CDATA payload starts in the raw file."""
    if not needle:
        return 1
    idx = raw.find(needle[:200])
    return raw.count("\n", 0, idx) + 1 if idx >= 0 else 1


def parse_xml(path: Path) -> SourceFile:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    sf = SourceFile(path=path, raw=raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        sf.units.append(Unit(name=path.name, kind="unparsable", decl="", impl=""))
        print(f"  ! {path}: XML parse error: {exc}", file=sys.stderr)
        return sf

    # Walk the tree rather than flattening it, so a getter can be named for the
    # property that owns it. A bare <Get Name="Get"> would otherwise make every
    # accessor in a file report as "Get", and any later lookup by name resolves
    # to whichever one came first — wrong file positions on the finding.
    def walk(el, owner: str = "") -> None:
        if el.tag in ("POU", "Method", "Get", "Set", "Property", "DUT", "GVL", "Itf"):
            own = el.get("Name") or path.stem
            name = f"{owner}.{own}" if owner and el.tag in ("Get", "Set") else own
            decl_el = el.find("Declaration")
            impl_el = el.find("Implementation/ST")
            decl = decl_el.text or "" if decl_el is not None else ""
            impl = impl_el.text or "" if impl_el is not None else ""
            if decl or impl:
                sf.units.append(Unit(
                    name=name, kind=el.tag, decl=decl, impl=impl,
                    decl_line=line_of(raw, decl), impl_line=line_of(raw, impl),
                ))
            owner = own if el.tag == "Property" else owner
        for child in el:
            walk(child, owner)

    walk(root)
    return sf


def parse_text(path: Path) -> SourceFile:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    # Split declaration from body at the last END_VAR, which is how a plain ST
    # export is laid out.
    ends = [m.end() for m in re.finditer(r"^\s*END_VAR\s*$", raw, re.M | re.I)]
    if ends:
        decl, impl = raw[: ends[-1]], raw[ends[-1]:]
    else:
        decl, impl = "", raw
    m = POU_HEADER.search(decl or raw)
    name = m.group(2) if m else path.stem
    return SourceFile(path=path, raw=raw, units=[Unit(
        name=name, kind="POU", decl=decl, impl=impl,
        decl_line=1, impl_line=raw.count("\n", 0, len(decl)) + 1,
    )])


def parse_variables(unit: Unit) -> list[Variable]:
    """Pull declarations out of a unit's VAR sections."""
    out: list[Variable] = []
    section = None
    clean = strip_noise(unit.decl)
    buf, buf_line = "", 0
    for n, line in enumerate(clean.splitlines(), start=1):
        if END_VAR.match(line):
            section, buf = None, ""
            continue
        m = VAR_SECTION.match(line)
        if m:
            section = m.group(1).upper()
            buf = ""
            continue
        if section is None:
            continue
        # A declaration may wrap across lines; accumulate until the semicolon.
        if not buf:
            buf_line = n
        buf += " " + line
        if ";" not in buf:
            continue
        dm = DECL_LINE.match(buf.strip() if buf.strip().endswith(";") else buf.strip() + ";")
        if dm:
            typ = re.sub(r"\s+", " ", dm.group(2)).strip()
            for nm in (x.strip() for x in dm.group(1).split(",")):
                if nm:
                    out.append(Variable(nm, typ, section, buf_line, unit.name))
        buf = ""
    return out


# --------------------------------------------------------------------------- helpers

def suppressed(lines: list[str], idx: int, rule: str) -> tuple[bool, bool]:
    """(is_suppressed, has_reason) for a 0-based line index."""
    for probe in (idx, idx - 1):
        if probe < 0 or probe >= len(lines):
            continue
        m = SUPPRESS.search(lines[probe])
        if m and rule in [r.strip().upper() for r in m.group(1).split(",")]:
            return True, bool(m.group(2).strip())
    return False, False


def base_type(t: str) -> str:
    t = t.strip().upper()
    t = re.sub(r"^ARRAY\s*\[.*?\]\s*OF\s+", "", t)
    t = re.sub(r"^(POINTER|REFERENCE)\s+TO\s+", "", t)
    return t.split("(")[0].strip()


def is_pointerish(t: str) -> bool:
    return bool(re.match(r"^\s*(POINTER|REFERENCE)\s+TO\s+", t, re.I))


NUM = r"(?:\d+\.\d+|\.\d+|\d+)"

# A divisor, as written: an identifier plus any .member and [index] chain, then an
# optional argument list that marks it a call rather than a variable. Capturing only
# the leading identifier made 'TO_REAL' the divisor of 'x / TO_REAL(n)' and hid the
# guard on 'IF stCfg.nDiv <> 0', so the rule contradicted the code it was reading.
DIVISOR = re.compile(
    r"/\s*([A-Za-z_]\w*(?:\s*\.\s*\w+|\s*\[[^\]]*\])*)\s*(\(\s*([^()]*?)\s*\))?"
)
# TO_REAL / DINT_TO_LREAL and friends: the argument is the value being divided by,
# so the guard belongs on it. Any other call has no divisor name worth reporting.
CONVERSION = re.compile(r"^(?:TO_[A-Z]+\d*|[A-Z]+\d*_TO_[A-Z]+\d*)$", re.I)


def guard_pattern(expr: str) -> str:
    """Regex matching `expr` in source, tolerating whitespace inside the path."""
    e = re.escape(expr)
    for lit, spaced in ((r"\.", r"\s*\.\s*"), (r"\[", r"\s*\[\s*"), (r"\]", r"\s*\]\s*")):
        e = e.replace(lit, spaced)
    return e


# --------------------------------------------------------------------------- checks

def check_file(sf: SourceFile, enabled: set[str]) -> list[Finding]:
    found: list[Finding] = []
    fname = str(sf.path)

    # Variables declared on the containing POU are visible to its methods, so
    # usage has to be judged against every implementation in the file.
    all_impl = strip_noise("\n".join(u.impl for u in sf.units))
    all_decl = strip_noise("\n".join(u.decl for u in sf.units))
    own_vars: list[list[Variable]] = [parse_variables(u) for u in sf.units]
    file_vars: list[Variable] = [v for group in own_vars for v in group]
    ref_vars = [v for v in file_vars if re.match(r"^\s*REFERENCE\s+TO", v.type, re.I)]

    # A method sees its own locals plus the containing POU's members — and nothing
    # from a sibling method. Typing names file-wide instead leaks: TcUnit declares
    # 'Expected'/'Actual' as LREAL in one assert method and as USINT in another, and
    # a shared set makes every integer comparison look like a float comparison.
    container_idx = next((i for i, u in enumerate(sf.units) if u.kind == "POU"), 0)
    container_vars = own_vars[container_idx] if own_vars else []

    def add(rule: str, unit: Unit, rel_line: int, text: str, msg: str, base: int) -> None:
        if rule not in enabled:
            return
        sev = RULES[rule][0]
        found.append(Finding(rule, sev, fname, unit.name, base + rel_line - 1, text, msg))

    for unit_idx, unit in enumerate(sf.units):
        scope_vars = list(container_vars) if unit_idx != container_idx else []
        scope_vars += own_vars[unit_idx] if unit_idx < len(own_vars) else []
        pointer_names = {v.name for v in scope_vars if is_pointerish(v.type)}
        # base_type() strips 'POINTER TO', so guard against calling a POINTER TO
        # LREAL a float — 'IF pData = 0' is a null check, not a float comparison.
        real_names = {v.name for v in scope_vars
                      if base_type(v.type) in REAL_TYPES and not is_pointerish(v.type)}
        time_names = {v.name for v in scope_vars
                      if base_type(v.type) in TIME_TYPES and not is_pointerish(v.type)}

        impl = strip_noise(unit.impl)
        decl = strip_noise(unit.decl)
        lines = impl.splitlines()
        decl_lines = decl.splitlines()
        raw_lines = unit.impl.splitlines()
        upper = impl.upper()

        # --- X0 / suppression hygiene ------------------------------------
        for i, line in enumerate(raw_lines):
            m = SUPPRESS.search(line)
            if m and not m.group(2).strip():
                add("X0", unit, i + 1, line,
                    f"suppresses {m.group(1)} with no reason given", unit.impl_line)

        # --- X1 unbounded loop -------------------------------------------
        for i, line in enumerate(lines):
            if re.search(r"\b(WHILE|REPEAT)\b", line, re.I):
                sup, _ = suppressed(raw_lines, i, "X1")
                if not sup:
                    add("X1", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        "loop may not terminate within one scan; model the wait as a "
                        "state machine, or suppress with a reason if the bound is provable",
                        unit.impl_line)

        # --- X2 timer preset must be a TIME literal ------------------------
        for i, line in enumerate(lines):
            for m in re.finditer(r"\b(PT|udiTimeOut|TimeOut)\s*:=\s*([^,;)\s]+)", line, re.I):
                val = m.group(2).strip()
                if re.fullmatch(NUM, val) or re.fullmatch(r"\d+", val):
                    add("X2", unit, i + 1, line,
                        f"{m.group(1)} := {val} is a number; a preset needs a TIME literal "
                        f"such as T#500MS, or DINT_TO_TIME(...)", unit.impl_line)

        # --- X3 CASE without ELSE ------------------------------------------
        depth = 0
        case_open: list[tuple[int, bool]] = []
        for i, line in enumerate(lines):
            u = line.upper()
            for _ in re.finditer(r"\bCASE\b", u):
                case_open.append((i, False))
                depth += 1
            if case_open and re.search(r"^\s*ELSE\b", u):
                case_open[-1] = (case_open[-1][0], True)
            for _ in re.finditer(r"\bEND_CASE\b", u):
                if case_open:
                    start, has_else = case_open.pop()
                    depth -= 1
                    if not has_else:
                        sup, _ = suppressed(raw_lines, start, "X3")
                        if not sup:
                            add("X3", unit, start + 1,
                                raw_lines[start] if start < len(raw_lines) else line,
                                "add an ELSE branch so an unexpected state is caught "
                                "rather than silently ignored", unit.impl_line)

        # --- X4 unguarded division ------------------------------------------
        const_names = {v.name for v in scope_vars if "CONSTANT" in v.section}
        for i, line in enumerate(lines):
            for m in DIVISOR.finditer(line):
                expr = re.sub(r"\s+", "", m.group(1))
                if m.group(2):
                    arg = re.sub(r"\s+", "", m.group(3) or "")
                    root = re.match(r"[A-Za-z_]\w*", expr).group(0)
                    if not (CONVERSION.match(root)
                            and re.fullmatch(r"[A-Za-z_][\w.\[\]]*", arg)):
                        continue      # a call whose result has no name to guard
                    expr = arg
                root = re.match(r"[A-Za-z_]\w*", expr).group(0)
                if root.upper() in KEYWORDS or root in const_names:
                    continue
                # Match the guard against the whole divisor expression. Matching only
                # the root reported 'stCfg.nDiv' as unguarded while the line above it
                # read 'IF stCfg.nDiv <> 0' — the rule contradicting the code's guard.
                e = guard_pattern(expr)
                window = "\n".join(lines[max(0, i - 12): i + 1])
                if re.search(rf"(?<![.\w]){e}\s*(<>|>|<)\s*0", window):
                    continue
                if re.search(rf"\bABS\s*\(\s*{e}\s*\)\s*>", window, re.I):
                    continue
                # 'IF n = 0 THEN RETURN; END_IF' is the other guard shape in wide use.
                if re.search(rf"(?<![.\w]){e}\s*=\s*0\s*THEN\b.{{0,60}}?"
                             rf"\b(RETURN|EXIT|CONTINUE)\b", window, re.I | re.S):
                    continue
                sup, _ = suppressed(raw_lines, i, "X4")
                if not sup:
                    add("X4", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        f"'{expr}' is not proven non-zero before the division; a "
                        f"divide-by-zero faults the runtime", unit.impl_line)
                break

        # --- X5 pointer dereference without a NULL check ---------------------
        for i, line in enumerate(lines):
            for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\^", line):
                name = m.group(1)
                if name.upper() in ("THIS", "SUPER") or name not in pointer_names:
                    continue
                window = "\n".join(lines[max(0, i - 15): i + 1])
                if re.search(rf"\b{re.escape(name)}\s*(<>|=)\s*0", window):
                    continue
                if re.search(rf"__ISVALIDREF\s*\(\s*{re.escape(name)}", window, re.I):
                    continue
                sup, _ = suppressed(raw_lines, i, "X5")
                if not sup:
                    add("X5", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        f"'{name}' dereferenced with no preceding '{name} <> 0' check; "
                        f"a stale pointer after an online change corrupts memory silently",
                        unit.impl_line)
                break

        # --- CP8 / CP28 equality on REAL or TIME -----------------------------
        for i, line in enumerate(lines):
            for m in re.finditer(r"([A-Za-z_]\w*(?:\.\w+)*)\s*(=|<>)\s*([A-Za-z_]\w*(?:\.\w+)*|" + NUM + r")", line):
                lhs, op, rhs = m.group(1), m.group(2), m.group(3)
                # Exclude ':=' where it actually sits, not anywhere on the line. A
                # whole-line skip also discarded 'bAtTarget := (fA = fB);' — storing a
                # comparison in a BOOL is everyday ST, and it is the exact defect this
                # rule exists for.
                if line[:m.start(2)].rstrip().endswith(":"):
                    continue          # ':=' assignment, not a comparison
                lroot, rroot = lhs.split(".")[0], rhs.split(".")[0]
                float_lit = bool(re.fullmatch(r"\d+\.\d+|\.\d+", rhs))
                if lroot in real_names or rroot in real_names or float_lit:
                    add("CP8", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        f"'{lhs} {op} {rhs}' compares floating point exactly; compare "
                        f"against a tolerance instead", unit.impl_line)
                elif lroot in time_names or rroot in time_names:
                    add("CP28", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        f"'{lhs} {op} {rhs}' compares TIME exactly; a scan will step over "
                        f"the exact value", unit.impl_line)

        # --- E1 dynamic allocation -------------------------------------------
        if unit.name.upper() not in ("FB_INIT", "FB_EXIT", "FB_REINIT"):
            for i, line in enumerate(lines):
                if re.search(r"\b__(NEW|DELETE)\b", line):
                    sup, _ = suppressed(raw_lines, i, "E1")
                    if not sup:
                        add("E1", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                            "allocation in cyclic code makes execution time unbounded",
                            unit.impl_line)

        # --- E3 ordering comparison on a pointer -------------------------------
        for i, line in enumerate(lines):
            for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(<=|>=|<|>)\s*([A-Za-z_]\w*)", line):
                if m.group(1) in pointer_names or m.group(3) in pointer_names:
                    add("E3", unit, i + 1, raw_lines[i] if i < len(raw_lines) else line,
                        "only = and <> are defined on pointers; ordering relies on "
                        "undocumented memory layout", unit.impl_line)

        # --- CP13 recursion ------------------------------------------------------
        if unit.kind in ("POU", "Method") and unit.name:
            if re.search(rf"(?<![.\^\w]){re.escape(unit.name)}\s*\(", impl):
                add("CP13", unit, 1, unit.name,
                    f"'{unit.name}' calls itself; replace the recursion with iteration",
                    unit.impl_line)

        # --- CP14 early RETURN ---------------------------------------------------
        ret_lines = [i for i, l in enumerate(lines) if re.search(r"^\s*RETURN\s*;", l, re.I)]
        meaningful = [i for i, l in enumerate(lines) if l.strip()]
        if ret_lines and meaningful:
            for r in ret_lines:
                if r != meaningful[-1]:
                    sup, _ = suppressed(raw_lines, r, "CP14")
                    if not sup:
                        add("CP14", unit, r + 1, raw_lines[r] if r < len(raw_lines) else "RETURN;",
                            "an early RETURN hides the rest of the body from a debugger "
                            "breakpoint at the end of the POU", unit.impl_line)
                    break

        # --- CP20 one FB instance called twice ------------------------------------
        fb_instances = {
            v.name for v in scope_vars
            if re.match(r"^(FB_|TON|TOF|TP|R_TRIG|F_TRIG|CTU|CTD|MC_)", v.type, re.I)
        }
        for inst in sorted(fb_instances):
            calls = len(re.findall(rf"(?<![.\w]){re.escape(inst)}\s*\(", impl))
            if calls > 1:
                idx = next((i for i, l in enumerate(lines) if re.search(rf"(?<![.\w]){re.escape(inst)}\s*\(", l)), 0)
                add("CP20", unit, idx + 1, raw_lines[idx] if idx < len(raw_lines) else inst,
                    f"'{inst}' is called from {calls} sites in this body; confirm at most "
                    f"one runs per scan, or the later call overwrites the earlier one's "
                    f"inputs", unit.impl_line)

        # --- X8 FB_init without an online-change guard ------------------------------
        if unit.name.upper() == "FB_INIT" and "BINCOPYCODE" in decl.upper():
            body = impl.strip()
            # Re-running a plain assignment on an online change is harmless, so only
            # flag work that is not idempotent: allocation, loops, or calling out.
            risky = re.search(r"\b__NEW\b|\b__DELETE\b|\b(FOR|WHILE|REPEAT)\b"
                              r"|\b[A-Za-z_]\w*\s*\([^)]*\)\s*;", impl, re.I)
            if body and "BINCOPYCODE" not in upper and risky:
                add("X8", unit, 1, body.splitlines()[0] if body.splitlines() else "FB_init",
                    "FB_init runs again on every online change; guard with "
                    "'IF bInCopyCode THEN RETURN; END_IF' or this work is repeated "
                    "against already-live state", unit.impl_line)

        # --- L11 line length -----------------------------------------------------
        for i, line in enumerate(raw_lines):
            if len(line.rstrip()) > MAX_LINE:
                add("L11", unit, i + 1, line[:90],
                    f"{len(line.rstrip())} characters; PLCopen suggests a maximum of {MAX_LINE}",
                    unit.impl_line)

        # --- CP23 parameter count -------------------------------------------------
        if unit.kind in ("POU", "Method"):
            pins = [v for v in (own_vars[unit_idx] if unit_idx < len(own_vars) else [])
                    if v.section in ("VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT")]
            if len(pins) > MAX_POU_PINS:
                add("CP23", unit, 1, unit.name,
                    f"{len(pins)} parameters; group related ones into a STRUCT to stay "
                    f"under about {MAX_POU_PINS}", unit.decl_line)

        # --- X9 the two PLCopen behaviour models mixed -----------------------------
        # Execute pairs with Done, Enable pairs with Valid. Mixing them costs nothing at
        # runtime, which is why it survives review and then misleads every caller who
        # knows the convention. An FB carrying BOTH triggers is left alone: a command
        # block behind an enable gate is a real design, and the text cannot say otherwise.
        if re.search(r"^\s*FUNCTION_BLOCK\b", decl, re.I | re.M):
            declared = own_vars[unit_idx] if unit_idx < len(own_vars) else []
            ins = [v for v in declared if v.section == "VAR_INPUT"]
            outs = [v for v in declared if v.section == "VAR_OUTPUT"]
            execute = next((v for v in ins if PIN_EXECUTE.match(v.name)), None)
            enable = next((v for v in ins if PIN_ENABLE.match(v.name)), None)
            done = next((v for v in outs if PIN_DONE.match(v.name)), None)
            valid = next((v for v in outs if PIN_VALID.match(v.name)), None)
            mixed = None
            if enable and done and not execute:
                mixed = (enable, done, "Enable", "Valid")
            elif execute and valid and not enable:
                mixed = (execute, valid, "Execute", "Done")
            if mixed:
                trigger, result, family, partner = mixed
                add("X9", unit, trigger.line, f"{trigger.name} : {trigger.type}",
                    f"'{trigger.name}' and '{result.name}' come from the two different "
                    f"PLCopen behaviour models; {family} pairs with {partner}, so rename "
                    f"one of them (see references/behaviour-model.md)", unit.decl_line)

    # --- X6 REFERENCE TO never validated --------------------------------------
    for v in ref_vars:
        if not re.search(rf"__ISVALIDREF\s*\(\s*{re.escape(v.name)}", all_impl, re.I):
            if re.search(rf"(?<![.\w]){re.escape(v.name)}\b", all_impl):
                unit = next((u for u in sf.units if u.name == v.unit), sf.units[0])
                # A METHOD parameter is bound at every call site — the compiler will
                # not let a caller omit it — so it cannot be the unwired-input defect
                # this rule is aimed at. Reported low rather than dropped, because a
                # caller can still pass its own unassigned reference straight through.
                bound = unit.kind == "Method" and v.section in ("VAR_INPUT", "VAR_IN_OUT")
                sev = "low" if bound else RULES["X6"][0]
                why = ("the call site always binds it, but a caller can pass an "
                       "unassigned reference through" if bound else
                       "an unassigned reference dereferences address zero")
                if "X6" in enabled:
                    found.append(Finding(
                        "X6", sev, fname, v.unit, unit.decl_line + v.line - 1,
                        f"{v.name} : {v.type}",
                        f"'{v.name}' is used but never checked with __ISVALIDREF; " + why))

    # --- CP24 unused variables -------------------------------------------------
    for v in file_vars:
        if v.section in ("VAR_EXTERNAL", "VAR_GLOBAL"):
            continue
        if v.name in FIXED_SIGNATURE_PARAMS.get(v.unit.upper(), ()):
            continue
        # An instance can be declared for its own sake — a TcUnit suite registers
        # itself from FB_init, so the declaration is the entire point and there is
        # nothing to reference. Only scalars are safe to call dead on sight.
        if re.match(r"^(FB_|.*_Test$)", v.type.strip(), re.I):
            continue
        uses = len(re.findall(rf"(?<![.\w]){re.escape(v.name)}\b", all_impl))
        # A name also appearing in another unit's declaration (a method parameter,
        # say) is out of scope for this crude count, so only flag a clean zero.
        if uses == 0 and not re.search(rf"(?<![.\w]){re.escape(v.name)}\b",
                                       all_decl.replace(v.name + " :", "", 1)):
            unit = next((u for u in sf.units if u.name == v.unit), sf.units[0])
            if "CP24" in enabled:
                found.append(Finding(
                    "CP24", RULES["CP24"][0], fname, v.unit, unit.decl_line + v.line - 1,
                    f"{v.name} : {v.type}",
                    f"'{v.name}' is declared in {v.section} but never referenced"))

    # --- X7 state machine with no error state -----------------------------------
    if re.search(r"\bCASE\b", all_impl, re.I):
        state_words = re.findall(r"\b(\w*(?:ERROR|FAULT|ALARM|ABORT)\w*)\b", all_impl, re.I)
        if not state_words and re.search(r"\bCASE\s+\w*(STATE|STEP|SEQ)\w*\s+OF", all_impl, re.I):
            unit = sf.units[0]
            if "X7" in enabled:
                found.append(Finding(
                    "X7", RULES["X7"][0], fname, unit.name, unit.impl_line, "CASE ... OF",
                    "no error or fault state is reachable from this state machine; a "
                    "failed step has nowhere to go and no way to report itself"))

    return found


# --------------------------------------------------------------------------- driver

def collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    wanted = XML_SUFFIXES | TEXT_SUFFIXES
    for p in paths:
        path = Path(p)
        if path.is_dir():
            # Match on the lowercased suffix rather than globbing per spelling:
            # the real files are ".TcPOU", which a case-sensitive rglob for
            # "*.tcpou" or "*.TCPOU" silently misses on Linux.
            out.extend(sorted(f for f in path.rglob("*")
                              if f.is_file() and f.suffix.lower() in wanted))
        elif path.exists():
            out.append(path)
        else:
            print(f"  ! no such path: {p}", file=sys.stderr)
    seen, uniq = set(), []
    for f in out:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(f)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Static review for IEC 61131-3 Structured Text.",
        epilog="Rule ids: " + ", ".join(sorted(RULES)),
    )
    ap.add_argument("paths", nargs="*", help=".TcPOU/.TcDUT/.TcGVL/.TcIO/.st files or directories")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--min-severity", choices=SEVERITIES, default="low",
                    help="hide findings below this severity (default: low)")
    ap.add_argument("--fail-on", choices=SEVERITIES + ("never",), default="high",
                    help="exit 1 when a finding at or above this severity exists (default: high)")
    ap.add_argument("--rules", help="comma-separated rule ids to run (default: all but "
                                    + ", ".join(sorted(PEDANTIC)) + ")")
    ap.add_argument("--pedantic", action="store_true",
                    help="also run the style rules held back by default ("
                         + ", ".join(sorted(PEDANTIC)) + ")")
    ap.add_argument("--list-rules", action="store_true", help="print the rule table and exit")
    args = ap.parse_args()

    if args.list_rules:
        print(f"{'RULE':6s} {'SEVERITY':9s} DESCRIPTION")
        for rid in sorted(RULES, key=lambda r: (SEVERITIES.index(RULES[r][0]), r)):
            sev, desc = RULES[rid]
            print(f"{rid:6s} {sev:9s} {desc}")
        return 0

    if not args.paths:
        ap.error("give at least one file or directory (or --list-rules)")

    enabled = set(RULES) if args.pedantic else set(RULES) - PEDANTIC
    if args.rules:
        want = {r.strip().upper() for r in args.rules.split(",") if r.strip()}
        unknown = want - set(RULES)
        if unknown:
            print(f"unknown rule id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        enabled = want

    files = collect(args.paths)
    if not files:
        print("no source files found", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for f in files:
        suf = f.suffix.lower()
        try:
            sf = parse_xml(f) if suf in XML_SUFFIXES else parse_text(f)
        except Exception as exc:                      # keep going over a big tree
            print(f"  ! {f}: {exc}", file=sys.stderr)
            continue
        if sf.units:
            findings.extend(check_file(sf, enabled))

    cut = SEVERITIES.index(args.min_severity)
    findings = [f for f in findings if SEVERITIES.index(f.severity) <= cut]
    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.file, f.line))

    if args.json:
        print(json.dumps({
            "files_scanned": len(files),
            "findings": [f.as_dict() for f in findings],
            "summary": {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES},
        }, indent=2))
    else:
        if not findings:
            print(f"{len(files)} file(s) scanned — no findings.")
            print("This is a pattern check, not a compile. It does not prove the code builds.")
        else:
            current = None
            for f in findings:
                if f.file != current:
                    current = f.file
                    print(f"\n{f.file}")
                print(f"  {f.severity:6s} {f.rule:5s} {f.obj}:{f.line}  {f.message}")
                if f.text.strip():
                    print(f"         | {f.text.strip()[:100]}")
            counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
            print(f"\n{len(files)} file(s) scanned — "
                  + ", ".join(f"{counts[s]} {s}" for s in SEVERITIES))
            print("Pattern check only; a clean run does not mean the code compiles.")

    if args.fail_on != "never":
        gate = SEVERITIES.index(args.fail_on)
        if any(SEVERITIES.index(f.severity) <= gate for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
