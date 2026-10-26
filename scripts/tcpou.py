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
  add-method, add-property
            Append an empty METHOD or PROPERTY to a POU or interface
  register  Add a file to a .plcproj so it actually compiles
  pins      List the pin wiring of every FBD/LD box (read-only)
  code-equal
            Prove an edit changed only comments and whitespace
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

    def __init__(self, path, raw=None):
        self.path = path
        if raw is None:
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
        body = body.replace("\r\n", "\n")
        # A pipe (PowerShell's `Get-Content d.st | set`) and most editors append one
        # line break after the last line, while `get` prints the part exactly, so
        # the round trip grew an empty line before ]]> on every edit. One trailing
        # line break more than the part has now is that artefact and is dropped;
        # any other count is stored as sent, so a wanted empty last line stays
        # possible by sending two.
        old = self.text[span[0]:span[1]].replace("\r\n", "\n")
        if _trailing(body) == _trailing(old) + 1:
            body = body[:-1]
        body = body.replace("\n", self.eol)
        self.text = self.text[:span[0]] + body + self.text[span[1]:]

    # -- output --------------------------------------------------------------

    def save(self):
        data = self.text.encode("utf-8")
        if self.has_bom:
            data = BOM + data
        open(self.path, "wb").write(data)


def _trailing(text):
    """How many line breaks `text` ends with."""
    return len(text) - len(text.rstrip("\n"))


def decode_source(data, what):
    """Text of an incoming source part, decoded by its BOM.

    UTF-8 with or without a BOM, and UTF-16 LE or BE with one. Windows PowerShell
    5.1's `>` is Out-File and writes UTF-16LE with a BOM, so a body saved with
    `get > d.st` arrived here as 0xFF 0xFE and `set` died in a traceback. Bytes
    that are none of these are refused by name rather than guessed at.
    """
    try:
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return data.decode("utf-16")       # the codec reads the BOM and drops it
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{what}: not UTF-8 or UTF-16 with a BOM") from None


# Fingerprints of UTF-8 read through the wrong code page: '²' and '³' become 'Â²'/'Â³'
# under cp1252 and '┬▓'/'┬│' under the OEM page a PowerShell 5.1 console uses. A
# body carrying one the part did not have before was mangled on its way here.
MOJIBAKE = ("\u00c2\u00b2", "\u00c2\u00b3", "\u252c\u2593", "\u252c\u2502")


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


def add_member(path, kind, name, typ=None, access=None, setter=True):
    """Append an empty METHOD or PROPERTY to a POU or interface, in place.

    The shape is the one XAE writes: a <Method> or <Property> as the last child of
    the <POU>/<Itf>, each carrying a fresh Id. Interface members get no
    <Implementation>, which is how XAE stores a body-less member. Nothing outside
    the inserted block changes, and it is written in the file's own line endings.
    Fill the new parts in with `set` afterwards.
    """
    f = TcFile(path)
    host = re.search(r"</(POU|Itf)>(?![\s\S]*</(?:POU|Itf)>)", f.text)
    if not host:
        raise ValueError("no <POU> or <Itf> to add a member to")
    itf = host.group(1) == "Itf"
    if re.search(rf'<(?:Method|Property)\s+Name="{re.escape(name)}"', f.text, re.I):
        raise ValueError(f"a method or property named {name} already exists")
    if itf and access:
        raise ValueError("interface members take no access modifier")

    head = " ".join(x for x in ((kind.upper(), access, name)) if x)
    if typ:
        head += f" : {typ}"
    ind = "    "

    def accessor(el):
        if itf:
            return [f'{ind}  <{el} Name="{el}" Id="{guid()}">',
                    f"{ind}    <Declaration><![CDATA[]]></Declaration>",
                    f"{ind}  </{el}>"]
        return [f'{ind}  <{el} Name="{el}" Id="{guid()}">',
                f"{ind}    <Declaration><![CDATA[VAR\nEND_VAR\n]]></Declaration>",
                f"{ind}    <Implementation>",
                f"{ind}      <ST><![CDATA[]]></ST>",
                f"{ind}    </Implementation>",
                f"{ind}  </{el}>"]

    if kind == "method":
        block = [f'{ind}<Method Name="{name}" Id="{guid()}">',
                 f"{ind}  <Declaration><![CDATA[{head}\nVAR_INPUT\nEND_VAR\n]]></Declaration>"]
        if not itf:
            block += [f"{ind}  <Implementation>",
                      f"{ind}    <ST><![CDATA[]]></ST>",
                      f"{ind}  </Implementation>"]
        block.append(f"{ind}</Method>")
    else:
        block = [f'{ind}<Property Name="{name}" Id="{guid()}">',
                 f"{ind}  <Declaration><![CDATA[{head}\n]]></Declaration>"]
        block += accessor("Get") + (accessor("Set") if setter else [])
        block.append(f"{ind}</Property>")

    # Insert at the start of the closing tag's line, so its own indent stays put.
    cut = f.text.rfind("\n", 0, host.start()) + 1
    text = "\n".join(block) + "\n"
    f.text = f.text[:cut] + text.replace("\n", f.eol) + f.text[cut:]
    f.save()
    return name


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


# -- FBD/LD wiring -----------------------------------------------------------

# Flags bit 0 on an operand: XAE's PLCopen export marks it negated="true", as a
# negated contact and/or pin. On one 4024 LD project every Flags=1 operand was shown
# negated and no Flags=0 operand was.
NEGATED = 1
# Flags 8 was seen only on the "???" output operand of a conditional RETURN rung; it
# is not a negation. See _rungs.
RETURN_MARK = 8


def _q(text):
    return (text or "").strip().strip('"')


def _flags(el):
    """The Flags value of an operand element, 0 when it carries none."""
    v = _q(el.findtext("o[@n='Flags']/v[@n='Flags']"))
    return int(v.rstrip("L")) if v else 0


def _named(el):
    """An operand's symbol, prefixed NOT when its Flags say XAE shows it negated."""
    name = _q(el.findtext("v[@n='Operand']"))
    if not name:
        return ""
    return f"NOT {name}" if _flags(el) & NEGATED else name


def _operand(item, ld=False, rail=False):
    """Text of what feeds one input pin: a symbol, NOT symbol, or a nested operator box.

    `rail` says this is the first input of the leftmost box on an LD rung. There a
    BoxTreeTerminator is the connection to the left power rail - TRUE whenever the
    rung is energised - and not an unwired pin. Measured at InputItems[0] of 48
    boxes on one 4024 LD project, where XAE's PLCopen export draws exactly that and
    the XAE editor shows the input wired straight to the rail. No FBD terminator
    has been seen, so in an Fbd network it stays "(unwired)".
    """
    if item.get("t") == "BoxTreeTerminator":
        return "(rung: left rail, TRUE)" if ld and rail else "(unwired)"
    btype = item.findtext("v[@n='BoxType']")
    if btype is not None:
        kids = item.find("l2[@n='InputItems']")
        args = ([_operand(k, ld, rail and i == 0) for i, k in enumerate(kids)]
                if kids is not None else [])
        return f"{_q(btype)}({', '.join(args)})"
    op = item.find("o[@n='Operand']")
    return _named(op if op is not None else item) or "(unwired)"


def _pin_names(box, param):
    names = box.find(f"o[@n='{param}']/l2[@n='Names']")
    return [] if names is None else [_q(n.text) for n in names]


def _has_pins(el):
    """True for an instance or function box: it has named pins to list on its own."""
    return el.findtext("v[@n='BoxType']") is not None and bool(
        _pin_names(el, "InputParam") or _pin_names(el, "OutputParam"))


def _bodies(root):
    """(owner, <Implementation>) for every part, the owner named as `show` names it."""
    found = []

    def walk(el, names):
        for child in el:
            if child.tag in CONTAINERS:
                walk(child, [] if names is None else names + [child.get("Name", "")])
            elif child.tag == "Implementation" and names is not None:
                found.append((".".join(n for n in names if n), child))
            else:
                walk(child, names)

    walk(root, None)
    return found


def _boxes(network, owner, ld, pin_re, box_re):
    """Every instance or function box in one network, with its pin wiring."""
    out = []
    for box in network.iter():
        if not _has_pins(box):
            continue            # an operator (AND, OR, ...) is printed inline where it feeds a pin
        btype = _q(box.findtext("v[@n='BoxType']"))
        inst = _q(box.findtext("o[@n='Instance']/v[@n='Operand']"))
        if box_re and not (box_re.search(inst) or box_re.search(btype)):
            continue
        wires = []
        ins = box.find("l2[@n='InputItems']")
        if ins is not None:
            wires += [("in", n, _operand(i, ld, k == 0))
                      for k, (n, i) in enumerate(zip(_pin_names(box, "InputParam"), ins))]
        outs = box.find("o[@n='OutputItems']/l2[@n='OutputItems']")
        if outs is not None:
            # An unwired output is an empty operand, or a bare <n /> - skipped either way.
            wires += [("out", n, _named(o))
                      for n, o in zip(_pin_names(box, "OutputParam"), outs) if _named(o)]
        wires = [w for w in wires if not pin_re or pin_re.search(w[1])]
        if wires:
            out.append((owner, f"{inst or '(no instance)'} : {btype}", wires))
    return out


def _rungs(network, owner, ld, pin_re, box_re):
    """Coil and RETURN rungs: a BoxTreeAssign whose RValue holds no instance box.

    Both are stored as NetworkItems of cet="BoxTreeAssign". A coil rung names the
    variable it drives in OutputItems (Flags 0) and carries the contacts as RValue,
    nested operator boxes such as AND(OR(a, b, c), NOT d); XAE exports it as
    contacts feeding a <coil>. A conditional RETURN rung has one OutputItems operand
    "???" with Flags 8 and the condition as RValue; XAE exports it as a contact
    feeding a <return>. Both readings were checked on one 4024 project two ways:
    against XAE's PLCopen export of 18 RETURN rungs and one coil rung, and in the
    XAE editor on the same rungs (a negated contact into RETURN; three contacts in
    parallel, then a negated contact, then a coil). A rung whose RValue is an
    instance box is not listed here: the box lists itself.
    """
    out = []
    if box_re:
        return out          # --box asks for a box, and these rungs have none
    for items in network.iter("l2"):
        if items.get("n") != "NetworkItems":
            continue
        for assign in items:
            rvalue = assign.find("o[@n='RValue']")
            if rvalue is None or any(_has_pins(el) for el in rvalue.iter()):
                continue
            cond = _operand(rvalue, ld, True)
            for o in assign.iterfind("o[@n='OutputItems']/l2[@n='OutputItems']/o"):
                name = _q(o.findtext("v[@n='Operand']"))
                if name == "???" and _flags(o) & RETURN_MARK:
                    if not pin_re:
                        out.append((owner, f"(return) <- {cond}", []))
                elif not pin_re or pin_re.search(name):
                    out.append((owner, f"(coil) {_named(o) or '(unwired)'} <- {cond}", []))
    return out


def pins(path, pin_re=None, box_re=None):
    """Pin wiring of every FBD/LD box, plus the coil and RETURN rungs between them.

    Returns ([(owner, header, [(dir, pin, operand)])], [owner of each CFC body]).
    Which variable feeds which pin of a box lives in the network XML, so a text
    search for 'ibEmpty :=' finds nothing in a graphical caller. Layout as XAE 4024
    writes an <NWL> body (FBD, LD and IL share it; <v n="DefaultViewMode"> says
    which): a box carries <v n="BoxType"> and <o n="Instance">; its inputs are the
    <l2 n="InputItems"> children, in the order of InputParam/Names; outputs are
    OutputItems/OutputItems in the order of OutputParam/Names. An operator such as
    OR feeding a pin is a nested box with no names of its own, so it is printed as
    a call and not listed separately. Unwired outputs are left out. The owner is
    the method, action or accessor the network lives in, "" for the POU body - on
    one project every caller's networks sat in three methods and the body was
    empty, so a box called in two methods read as a duplicate without it.

    CFC is not supported. A <CFC> body is a different schema (CFCImplementationObject,
    not a network list); how a box sits inside its CFCItemList has never been
    observed, and the projects this was built against use LD for every graphical
    POU. Its owners are returned so the caller can refuse instead of printing
    nothing.
    """
    root = ET.fromstring(TcFile(path).text)
    entries, cfc = [], []
    for owner, body in _bodies(root):
        if body.find("CFC") is not None:
            cfc.append(owner)
        nwl = body.find("NWL")
        if nwl is None:
            continue
        ld = _q(nwl.findtext(".//v[@n='DefaultViewMode']")) == "Ld"
        for lst in nwl.iter("l2"):
            if lst.get("n") != "NetworkList":
                continue
            for network in lst:
                entries += _boxes(network, owner, ld, pin_re, box_re)
                entries += _rungs(network, owner, ld, pin_re, box_re)
    return entries, cfc


# -- code-equal --------------------------------------------------------------

def _word(c):
    return c.isalnum() or c == "_"


def code_only(src):
    """Source with comments dropped and whitespace reduced to what separates tokens.

    String literals are kept byte for byte, so '//' inside one is not a comment
    and 'a b' never equals 'ab'. (* *) comments nest, as CODESYS allows. A run of
    whitespace or comments becomes one space only between two identifier
    characters - dropping it there would make 'a b' and 'ab' look the same.
    """
    out, gap, i, n = [], False, 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            i, gap = (n if j < 0 else j), True
        elif two == "(*":
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("(*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*)", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            gap = True
        elif two == "/*":
            j = src.find("*/", i + 2)
            i, gap = (n if j < 0 else j + 2), True
        elif src[i].isspace():
            i, gap = i + 1, True
        else:
            if gap and out and _word(out[-1][-1]) and _word(src[i]):
                out.append(" ")
            gap = False
            if src[i] in "'\"":
                j = i + 1
                while j < n and src[j] != src[i]:
                    j += 2 if src[j] == "$" else 1     # $' is the ST escape
                out.append(src[i:j + 1])
                i = j + 1
            else:
                out.append(src[i])
                i += 1
    return "".join(out)


def code_parts(tc):
    # Line endings are compared as LF on both sides, inside string literals too.
    # With core.autocrlf=true (the Git for Windows default) the HEAD blob has LF and
    # the working copy CRLF; whitespace between tokens absorbed that, but a
    # {attribute 'TcLinkTo' := '...'} whose value spans lines kept the CR inside
    # the literal, and one untouched file in 1352 came back DIFFERENT.
    return {k: code_only(tc.text[s:e].replace("\r\n", "\n")) for k, (s, e) in tc.parts().items()}


OBJECT_SUFFIXES = (".tcpou", ".tcdut", ".tcgvl", ".tcio")


def object_files(root):
    """Every TwinCAT object file under a directory, sorted. A whole project does not
    fit on one Windows command line: field round 4 ran 1,353 files in 14 batches."""
    return sorted(os.path.join(d, f) for d, _, names in os.walk(root)
                  for f in names if f.lower().endswith(OBJECT_SUFFIXES))


def git_blob(path, rev):
    """The bytes of `path` at `rev`, or None when git has no such file there."""
    import subprocess
    d, base = os.path.split(os.path.abspath(path))
    r = subprocess.run(["git", "show", f"{rev}:./{base}"], cwd=d, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def code_diff(old, new):
    """Report lines for every part whose code differs; empty when all are equal."""
    a, b = code_parts(old), code_parts(new)
    lines = []
    for key in list(a) + [k for k in b if k not in a]:
        if key not in b:
            lines.append(f"  {key}: removed")
        elif key not in a:
            lines.append(f"  {key}: added")
        elif a[key] != b[key]:
            x, y = a[key], b[key]
            k = next((j for j in range(min(len(x), len(y))) if x[j] != y[j]), min(len(x), len(y)))
            lines.append(f"  {key}: first difference at code character {k}")
            lines.append(f"    old: {x[max(0, k - 40):k + 40]}")
            lines.append(f"    new: {y[max(0, k - 40):k + 40]}")
    return lines


# -- checks ------------------------------------------------------------------

def check(path):
    problems, notes = [], []
    raw = open(path, "rb").read()
    # Encoding and line endings are reported, not enforced. The XAE editor saves
    # UTF-8-with-BOM and CRLF (its new-project wizard writes no BOM), but most published TwinCAT code is BOM+LF — git normalisation rewrites it and
    # TwinCAT reads it back happily. Measured over 2839 object files from the reference
    # corpus: 97% carry a BOM, but only 19% use CRLF, and the split runs per repository
    # rather than per file. What matters is that an edit PRESERVES whatever the file
    # already uses, which TcFile does. Calling LF an error would fail most real code.
    if not raw.startswith(BOM):
        notes.append("no UTF-8 BOM (objects saved from the XAE editor carry one; files the "
                     "new-project wizard creates may not; edits here preserve its absence)")
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
    p.add_argument("--out", help="write the part to this file instead of stdout: UTF-8, no BOM, "
                                 "LF. From Windows PowerShell 5.1 use this, never '>' or a pipe")

    p = sub.add_parser("set", help="replace one part's source")
    p.add_argument("file")
    p.add_argument("--part", required=True)
    p.add_argument("--from-file", help="read new source from this file (default: stdin); "
                                       "UTF-8 with or without a BOM, or UTF-16 with one")

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

    access = ["PUBLIC", "PRIVATE", "PROTECTED", "INTERNAL"]
    p = sub.add_parser("add-method", help="append an empty METHOD to a POU or interface")
    p.add_argument("file")
    p.add_argument("--name", required=True)
    p.add_argument("--returns", help="return type, e.g. BOOL (default: none)")
    p.add_argument("--access", type=str.upper, choices=access,
                   help="access modifier (default: none, which TwinCAT reads as PUBLIC)")

    p = sub.add_parser("add-property", help="append an empty PROPERTY to a POU or interface")
    p.add_argument("file")
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, help="property type, e.g. LREAL")
    p.add_argument("--access", type=str.upper, choices=access)
    p.add_argument("--no-set", action="store_true", help="getter only (read-only property)")

    p = sub.add_parser("register", help="add files to a .plcproj")
    p.add_argument("plcproj")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("reguid", help="give every object in a file a fresh Id GUID")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("pins", help="list the pin wiring of every FBD/LD box (read-only)")
    p.add_argument("file")
    p.add_argument("--pin", help="regex on the pin name")
    p.add_argument("--box", help="regex on the instance name or box type")

    p = sub.add_parser("code-equal", help="prove an edit changed only comments and whitespace")
    p.add_argument("files", nargs="+", help="object files, or directories to search for them")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--ref", default="HEAD", help="git revision to compare with (default: HEAD)")
    g.add_argument("--against", help="compare one file with this file on disk instead")

    p = sub.add_parser("check", help="validate structure and encoding")
    p.add_argument("files", nargs="+")

    a = ap.parse_args()

    # Source text is UTF-8 whatever the locale says. On Windows the default is
    # cp1252, which turned every '²' in a unit comment into 'Â²' on a get/set that
    # edited nothing, and aborted 'get' on a character cp1252 has no code for.
    # `set` reads its source as bytes and decodes by BOM (decode_source); stderr
    # is UTF-8 too, so a warning that quotes the text survives a redirect.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

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
            text = TcFile(a.file).get(a.part)
            if a.out:
                # Bytes, not a text stream: PowerShell 5.1's '>' decodes the script's
                # UTF-8 output through the console code page before writing it, so
                # '²' landed in the file as '┬▓' and no reader could repair it.
                open(a.out, "wb").write(text.encode("utf-8"))
            else:
                sys.stdout.write(text)
        except KeyError:
            print(f"no such part: {a.part}", file=sys.stderr)
            print("available: " + ", ".join(TcFile(a.file).parts()), file=sys.stderr)
            return 1
        return 0

    if a.cmd == "set":
        if a.from_file:
            data, what = open(a.from_file, "rb").read(), a.from_file
        else:
            data, what = sys.stdin.buffer.read(), "stdin"
        f = TcFile(a.file)
        try:
            body = decode_source(data, what)
            garbled = [m for m in MOJIBAKE if m in body and m not in f.get(a.part)]
            if garbled:
                print(f"warning: the new text contains {', '.join(garbled)} and the current "
                      f"part does not: UTF-8 read through cp1252 or an OEM code page on the "
                      f"way here? ('get --out' and 'set --from-file' avoid that)",
                      file=sys.stderr)
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
        path = os.path.normpath(os.path.join(a.dir, f"{a.name}.{ext}"))
        if os.path.exists(path):
            print(f"refused: {path} already exists", file=sys.stderr)
            return 1
        os.makedirs(a.dir, exist_ok=True)
        open(path, "wb").write(BOM + content.replace("\n", "\r\n").encode("utf-8"))
        print(f"created {path}")
        print("next: register it in the .plcproj or it will not be compiled:")
        print(f"  tcpou.py register <PLC.plcproj> {path}")
        return 0

    if a.cmd in ("add-method", "add-property"):
        try:
            if a.cmd == "add-method":
                add_member(a.file, "method", a.name, a.returns, a.access)
            else:
                add_member(a.file, "property", a.name, a.type, a.access, not a.no_set)
        except ValueError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        parts = [k for k in TcFile(a.file).parts() if k.split(":")[0].split(".")[0] == a.name]
        print(f"added {a.cmd.split('-')[1]} {a.name} to {a.file}")
        print("fill it in with: tcpou.py set <file> --part " + " | --part ".join(parts))
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

    if a.cmd == "pins":
        pin_re = a.pin and re.compile(a.pin, re.IGNORECASE)
        box_re = a.box and re.compile(a.box, re.IGNORECASE)
        entries, cfc = pins(a.file, pin_re, box_re)
        for owner, head, wires in entries:
            print(head + (f"   [{owner}]" if owner else ""))
            for d, pin, operand in wires:
                print(f"   {d:<3} {pin:<30} {'<-' if d == 'in' else '->'} {operand}")
        if cfc:
            # Exit 2 like code-equal's CANNOT COMPARE: an empty listing of a body this
            # tool cannot read must not look like "nothing wired".
            for owner in cfc:
                where = f" ({owner})" if owner else ""
                print(f"CFC body{where}: pins reads FBD/LD networks only")
            return 2
        if not entries:
            print("no FBD/LD boxes" + (" matched" if a.pin or a.box else " in this file"))
        return 0

    if a.cmd == "code-equal":
        # Exit 1 when code differs, 2 when a file could not be compared at all:
        # "nothing to compare with" must never read as "identical".
        if a.against and (len(a.files) != 1 or os.path.isdir(a.files[0])):
            print("refused: --against compares exactly one file", file=sys.stderr)
            return 2
        status, files = 0, []
        for path in a.files:
            if not os.path.isdir(path):
                files.append(path)
            elif object_files(path):
                files += object_files(path)
            else:
                print(f"CANNOT COMPARE {path}: no .TcPOU/.TcDUT/.TcGVL/.TcIO file under it")
                status = 2
        counts = {"IDENTICAL": 0, "DIFFERENT": 0, "CANNOT COMPARE": 0}
        for path in files:
            if a.against:
                old, base = TcFile(a.against), a.against
            else:
                blob = git_blob(path, a.ref)
                if blob is None:
                    print(f"CANNOT COMPARE {path}: not in git at {a.ref}")
                    counts["CANNOT COMPARE"] += 1
                    status = 2
                    continue
                old, base = TcFile(path, blob), a.ref
            new = TcFile(path)
            lines = code_diff(old, new)
            n = len(new.parts())
            counts["DIFFERENT" if lines else "IDENTICAL"] += 1
            print(f"{'DIFFERENT' if lines else 'IDENTICAL'} code: {path} vs {base} ({n} parts)")
            if lines:
                print("\n".join(lines))
                status = max(status, 1)
        if len(files) > 1:
            print(f"{len(files)} files: " + ", ".join(f"{v} {k.lower()}" for k, v in counts.items()))
        return status

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
    except BrokenPipeError:
        # `get ... | head` closed the pipe early: the reader's choice, not an error
        # ("! None: Broken pipe" is what the OSError branch made of it). Python
        # flushes stdout again at exit and would raise a second time, so point it
        # at a sink first.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(0)
    except OSError as exc:
        print(f"  ! {exc.filename}: {exc.strerror}", file=sys.stderr)
        sys.exit(1)
