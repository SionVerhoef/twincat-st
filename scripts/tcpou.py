#!/usr/bin/env python3
"""Read and write TwinCAT 3 PLC object files without corrupting them.

TwinCAT stores ST source inside CDATA blocks in XML files that also carry object
GUIDs, online-change line maps, a UTF-8 BOM and CRLF line endings. A generic XML
round-trip destroys most of that, so this tool edits the raw bytes surgically and
touches nothing outside the CDATA payload it was asked to change.

Subcommands:
  show      Summarise a file: object type, name, and every editable part
  get       Print one part's source (LF-normalised)
  set       Replace one part's source, preserving GUIDs, BOM and CRLF
  new       Scaffold a new .TcPOU / .TcDUT / .TcGVL with a fresh GUID
  register  Add a file to a .plcproj so it actually compiles
  check     Validate structure, encoding and line endings

Targets TwinCAT 3.1 build 4024.
"""

import argparse
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET

BOM = b"\xef\xbb\xbf"

# Elements that own a source part and can nest.
CONTAINERS = ("POU", "Method", "Property", "Get", "Set", "Action", "GVL", "DUT", "Itf")

TAG_RE = re.compile(
    r"<(?P<close>/?)(?P<el>" + "|".join(CONTAINERS) + r")\b(?P<attrs>[^>]*?)(?P<self>/?)>"
)
CDATA_RE = re.compile(
    r"<(?P<kind>Declaration|ST)\b[^>]*>\s*<!\[CDATA\[(?P<body>.*?)\]\]>", re.DOTALL
)
NAME_RE = re.compile(r'Name\s*=\s*"([^"]*)"')


class TcFile:
    """A TwinCAT PLC object file, held as text plus its original byte quirks."""

    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        self.has_bom = raw.startswith(BOM)
        if self.has_bom:
            raw = raw[len(BOM):]
        # Hold the text exactly as stored, line endings included. Normalising the
        # whole file to one ending and converting back on save rewrote every line
        # of a mixed-ending file: one stray CRLF in an LF file turned into 152, so
        # a one-line edit produced a whole-file diff. `eol` is only used to match
        # incoming source to whatever the file already predominantly uses.
        n_crlf = raw.count(b"\r\n")
        n_lf = raw.count(b"\n") - n_crlf
        self.mixed = bool(n_crlf and n_lf)
        self.eol = "\r\n" if n_crlf > n_lf else "\n"
        self.text = raw.decode("utf-8")

    # -- structure -----------------------------------------------------------

    def _stack_at(self, pos):
        """Container stack (element, name) enclosing byte offset `pos`."""
        stack = []
        for m in TAG_RE.finditer(self.text, 0, pos):
            if m.group("self"):
                continue
            if m.group("close"):
                if stack and stack[-1][0] == m.group("el"):
                    stack.pop()
            else:
                name = NAME_RE.search(m.group("attrs"))
                stack.append((m.group("el"), name.group(1) if name else ""))
        return stack

    def parts(self):
        """Ordered {part_key: (start, end)} spans of every CDATA payload."""
        found = {}
        for m in CDATA_RE.finditer(self.text):
            stack = self._stack_at(m.start())
            owner = ".".join(n for el, n in stack[1:] if n)
            suffix = "decl" if m.group("kind") == "Declaration" else "impl"
            key = f"{owner}:{suffix}" if owner else suffix
            found[key] = m.span("body")
        return found

    def get(self, key):
        span = self.parts().get(key)
        if span is None:
            raise KeyError(key)
        return self.text[span[0]:span[1]].replace("\r\n", "\n")

    def set(self, key, body):
        if "]]>" in body:
            raise ValueError("source contains ']]>' which would terminate the CDATA block")
        span = self.parts().get(key)
        if span is None:
            raise KeyError(key)
        body = body.replace("\r\n", "\n").replace("\n", self.eol)
        self.text = self.text[:span[0]] + body + self.text[span[1]:]

    # -- output --------------------------------------------------------------

    def save(self):
        data = self.text.encode("utf-8")
        if self.has_bom:
            data = BOM + data
        open(self.path, "wb").write(data)


# -- scaffolding -------------------------------------------------------------

def guid():
    return "{" + str(uuid.uuid4()) + "}"


GUID_ATTR = re.compile(r'\bId="\{[0-9a-fA-F-]{36}\}"')


def reguid(path):
    """Replace every Id GUID in a file with a fresh one.

    Copying a template leaves the copy carrying the original's GUIDs. TwinCAT
    identifies objects by Id, so two objects sharing one is a real conflict —
    and nothing warns you. Rewrites in place, preserving BOM and CRLF.
    """
    f = TcFile(path)
    n = len(GUID_ATTR.findall(f.text))
    if n == 0:
        return 0                      # nothing to stamp; leave the file untouched
    f.text = GUID_ATTR.sub(lambda _: f'Id="{guid()}"', f.text)
    f.save()
    return n


POU_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1" ProductVersion="3.1.4024.0">
  <POU Name="{name}" Id="{id}" SpecialFunc="None">
    <Declaration><![CDATA[{decl}]]></Declaration>
    <Implementation>
      <ST><![CDATA[{impl}]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
"""

SIMPLE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1" ProductVersion="3.1.4024.0">
  <{el} Name="{name}" Id="{id}">
    <Declaration><![CDATA[{decl}]]></Declaration>
  </{el}>
</TcPlcObject>
"""


# The two PLCopen interface families, and a plain block with neither. The pairing is
# the contract: Execute goes with Done, Enable goes with Valid. This scaffold shipped
# Enable with Done - the exact mix references/behaviour-model.md names as the mistake -
# and every FB scaffolded here inherited it, with no reason for the author to doubt a
# skeleton the skill itself produced. Reviewer rule X9 now fails that combination.
FB_SHAPES = {
    "execute": (
        "VAR_INPUT\n"
        "    bExecute : BOOL;    // rising edge starts the operation\n"
        "END_VAR\n"
        "VAR_OUTPUT\n"
        "    bBusy    : BOOL;    // true from the accepted edge until bDone or bError\n"
        "    bDone    : BOOL;    // completed; latched until bExecute goes false\n"
        "    bError   : BOOL;\n"
        "    nErrorID : UDINT;   // 0 = no error\n"
        "END_VAR\n"
    ),
    "enable": (
        "VAR_INPUT\n"
        "    bEnable  : BOOL;    // runs for as long as this is held true\n"
        "END_VAR\n"
        "VAR_OUTPUT\n"
        "    bValid   : BOOL;    // the outputs below are meaningful right now\n"
        "    bBusy    : BOOL;\n"
        "    bError   : BOOL;\n"
        "    nErrorID : UDINT;   // 0 = no error\n"
        "END_VAR\n"
    ),
    "cyclic": "VAR_INPUT\nEND_VAR\nVAR_OUTPUT\nEND_VAR\n",
}


def scaffold(kind, name, extends=None, implements=None, shape="execute"):
    if kind == "fb":
        head = f"FUNCTION_BLOCK {name}"
        if extends:
            head += f" EXTENDS {extends}"
        if implements:
            head += f" IMPLEMENTS {implements}"
        decl = f"{head}\n" + FB_SHAPES[shape] + "VAR\nEND_VAR\n"
        impl = "// Called unconditionally every cycle - see cyclic-execution-rules.md Rule 2\n"
        return "TcPOU", POU_TEMPLATE.format(name=name, id=guid(), decl=decl, impl=impl)
    if kind == "prg":
        decl = f"PROGRAM {name}\nVAR\nEND_VAR\n"
        return "TcPOU", POU_TEMPLATE.format(name=name, id=guid(), decl=decl, impl="")
    if kind == "fun":
        decl = f"FUNCTION {name} : BOOL\nVAR_INPUT\nEND_VAR\nVAR\nEND_VAR\n"
        return "TcPOU", POU_TEMPLATE.format(name=name, id=guid(), decl=decl, impl="")
    if kind == "dut":
        decl = f"TYPE {name} :\nSTRUCT\nEND_STRUCT\nEND_TYPE\n"
        return "TcDUT", SIMPLE_TEMPLATE.format(el="DUT", name=name, id=guid(), decl=decl)
    if kind == "gvl":
        decl = "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR\n"
        return "TcGVL", SIMPLE_TEMPLATE.format(el="GVL", name=name, id=guid(), decl=decl)
    raise ValueError(f"unknown kind: {kind}")


# -- .plcproj registration ---------------------------------------------------

def register(plcproj, files):
    raw = open(plcproj, "rb").read()
    has_bom = raw.startswith(BOM)
    if has_bom:
        raw = raw[len(BOM):]
    n_crlf = raw.count(b"\r\n")
    eol = "\r\n" if n_crlf > raw.count(b"\n") - n_crlf else "\n"
    text = raw.decode("utf-8")      # as stored; see TcFile.__init__

    base = os.path.dirname(os.path.abspath(plcproj))
    added = []
    for f in files:
        rel = os.path.relpath(os.path.abspath(f), base).replace("/", "\\")
        if f'Include="{rel}"' in text:
            print(f"  already registered: {rel}")
            continue
        entry = (
            f'    <Compile Include="{rel}">{eol}'
            f"      <SubType>Code</SubType>{eol}"
            f"    </Compile>{eol}"
        )
        # Insert into the ItemGroup that already holds Compile items.
        anchor = text.rfind("</Compile>")
        if anchor != -1:
            cut = text.index("\n", anchor) + 1
            text = text[:cut] + entry + text[cut:]
        else:
            cut = text.rindex("</Project>")
            text = text[:cut] + f"  <ItemGroup>{eol}{entry}  </ItemGroup>{eol}" + text[cut:]
        added.append(rel)

    if added:
        data = text.encode("utf-8")
        if has_bom:
            data = BOM + data
        open(plcproj, "wb").write(data)
        for rel in added:
            print(f"  registered: {rel}")
    return added


# -- checks ------------------------------------------------------------------

def check(path):
    problems, notes = [], []
    raw = open(path, "rb").read()
    # Encoding and line endings are reported, not enforced. XAE writes UTF-8-with-BOM and
    # CRLF, but most published TwinCAT code is BOM+LF — git normalisation rewrites it and
    # TwinCAT reads it back happily. Measured over 2839 object files from the reference
    # corpus: 97% carry a BOM, but only 19% use CRLF, and the split runs per repository
    # rather than per file. What matters is that an edit PRESERVES whatever the file
    # already uses, which TcFile does. Calling LF an error would fail most real code.
    if not raw.startswith(BOM):
        notes.append("no UTF-8 BOM (XAE writes one; edits here will preserve its absence)")
    body = raw[len(BOM):] if raw.startswith(BOM) else raw
    n_crlf = body.count(b"\r\n")
    n_lf = body.count(b"\n") - n_crlf
    if n_crlf and n_lf:
        notes.append(f"mixed line endings ({n_crlf} CRLF, {n_lf} LF); "
                     "edits here leave each line as it is")
    elif not n_crlf:
        notes.append("LF line endings, not CRLF (edits here will preserve LF)")

    text = body.decode("utf-8", errors="replace")
    if text.count("<![CDATA[") != text.count("]]>"):
        problems.append("unbalanced CDATA markers")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        problems.append(f"XML is not well-formed: {e}")
        return problems, notes

    if root.tag != "TcPlcObject":
        problems.append(f"root element is <{root.tag}>, expected <TcPlcObject>")
    pv = root.get("ProductVersion", "")
    if pv and not pv.startswith("3.1.4024"):
        notes.append(f"ProductVersion {pv} is not a 4024 build")

    for el in root.iter():
        if el.tag in CONTAINERS:
            if not el.get("Id"):
                problems.append(f"<{el.tag} Name=\"{el.get('Name', '?')}\"> has no Id GUID")
            if el.tag in ("POU", "Method") and el.find("Declaration") is None:
                problems.append(f"<{el.tag} Name=\"{el.get('Name', '?')}\"> has no <Declaration>")
    return problems, notes


# -- CLI ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="summarise a file's editable parts")
    p.add_argument("file")

    p = sub.add_parser("get", help="print one part's source")
    p.add_argument("file")
    p.add_argument("--part", default="impl", help="e.g. decl, impl, Reset:impl, Value.Get:impl")

    p = sub.add_parser("set", help="replace one part's source")
    p.add_argument("file")
    p.add_argument("--part", required=True)
    p.add_argument("--from-file", help="read new source from this file (default: stdin)")

    p = sub.add_parser("new", help="scaffold a new object")
    p.add_argument("--type", required=True, choices=["fb", "prg", "fun", "dut", "gvl"])
    p.add_argument("--name", required=True)
    p.add_argument("--dir", default=".")
    p.add_argument("--extends")
    p.add_argument("--implements")
    p.add_argument("--shape", default="execute", choices=list(FB_SHAPES),
                   help="fb only: which PLCopen interface family — 'execute' gives "
                        "bExecute/bBusy/bDone (default), 'enable' gives bEnable/bValid, "
                        "'cyclic' gives no command interface at all")

    p = sub.add_parser("register", help="add files to a .plcproj")
    p.add_argument("plcproj")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("reguid", help="give every object in a file a fresh Id GUID")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("check", help="validate structure and encoding")
    p.add_argument("files", nargs="+")

    a = ap.parse_args()

    if a.cmd == "show":
        f = TcFile(a.file)
        eol = "mixed CRLF+LF" if f.mixed else ("CRLF" if f.eol == "\r\n" else "LF")
        enc = ("BOM" if f.has_bom else "no-BOM") + ", " + eol
        print(f"{a.file}  [{enc}]")
        for key, (s, e) in f.parts().items():
            first = f.text[s:e].strip().splitlines()
            head = first[0][:70] if first else "(empty)"
            print(f"  {key:<28} {e - s:>6} chars  {head}")
        return 0

    if a.cmd == "get":
        try:
            sys.stdout.write(TcFile(a.file).get(a.part))
        except KeyError:
            print(f"no such part: {a.part}", file=sys.stderr)
            print("available: " + ", ".join(TcFile(a.file).parts()), file=sys.stderr)
            return 1
        return 0

    if a.cmd == "set":
        body = open(a.from_file).read() if a.from_file else sys.stdin.read()
        f = TcFile(a.file)
        try:
            f.set(a.part, body)
        except KeyError:
            print(f"no such part: {a.part}", file=sys.stderr)
            print("available: " + ", ".join(f.parts()), file=sys.stderr)
            return 1
        except ValueError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        f.save()
        print(f"updated {a.part} in {a.file}")
        return 0

    if a.cmd == "new":
        ext, content = scaffold(a.type, a.name, a.extends, a.implements, a.shape)
        path = os.path.join(a.dir, f"{a.name}.{ext}")
        if os.path.exists(path):
            print(f"refused: {path} already exists", file=sys.stderr)
            return 1
        os.makedirs(a.dir, exist_ok=True)
        open(path, "wb").write(BOM + content.replace("\n", "\r\n").encode("utf-8"))
        print(f"created {path}")
        print("next: register it in the .plcproj or it will not be compiled:")
        print(f"  tcpou.py register <PLC.plcproj> {path}")
        return 0

    if a.cmd == "register":
        register(a.plcproj, a.files)
        return 0

    if a.cmd == "reguid":
        # Zero replacements has to fail. The documented workflow is copy the
        # template, then reguid the copy - and reporting 'ok (0 regenerated)'
        # there tells you the identity was refreshed when it was not, leaving
        # the copy colliding with the template on the same Id in TwinCAT.
        failed = False
        for path in a.files:
            n = reguid(path)
            if n == 0:
                failed = True
                print(f"FAIL {path}")
                print("  - no Id attribute found; nothing was regenerated")
            else:
                print(f"ok   {path}  ({n} GUID{'s' if n != 1 else ''} regenerated)")
        return 1 if failed else 0

    if a.cmd == "check":
        failed = False
        for path in a.files:
            problems, notes = check(path)
            if problems:
                failed = True
                print(f"FAIL {path}")
                for x in problems:
                    print(f"  - {x}")
            else:
                print(f"ok   {path}")
            for n in notes:
                print(f"  note: {n}")
        return 1 if failed else 0


if __name__ == "__main__":
    # A stack trace in agent output invites the agent to start debugging this tool
    # instead of fixing its own argument. Report the same way st_review.py does.
    try:
        sys.exit(main())
    except FileNotFoundError as exc:
        print(f"  ! no such path: {exc.filename}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"  ! {exc.filename}: {exc.strerror}", file=sys.stderr)
        sys.exit(1)
