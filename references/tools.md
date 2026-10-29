# Tools — the reviewer and the two editors in full

`SKILL.md` carries the commands and the few rules that cause damage when missed. This file
has the rest: what every flag and exit status means, and each `tcpou.py` and `xae_edit.ps1`
subcommand's behaviour. Read it when a tool does something you did not expect, before working
around it.

## Running Python on Windows

**Every command in this skill is written `py -3`, because TwinCAT runs on Windows and Windows has no `python3`.** A bare `python3` there reaches the Microsoft Store alias stub, which prints *"Python was not found"* and exits 1 **even when Python is installed correctly** — so read the error as a wrong command, not a missing interpreter. On Linux or macOS use `python3` instead. The README has the detail.

## `scripts/st_review.py`

Every option:

```bash
py -3 scripts/st_review.py <file-or-dir>...             # defect rules
py -3 scripts/st_review.py src/ --pedantic              # + style rules
py -3 scripts/st_review.py src/ --json                  # machine-readable
py -3 scripts/st_review.py src/ --fail-on high          # CI gate (already the default)
py -3 scripts/st_review.py src/ --min-severity medium   # hide the low findings
py -3 scripts/st_review.py src/ --rules X1,X5,CP8       # only these rules
py -3 scripts/st_review.py --list-rules                 # what it checks
```

**Point it at the code you own, not at the whole `.plcproj`.** A project pulls in vendor and framework libraries nobody on the team can change, and their findings bury yours: on one real project of about 1,350 files, scanning everything gave 835 findings where the 111 application files gave 68. Scan the application folder.

**Exit status is 1 only at `--fail-on` or above, and that defaults to `high`.** A run reporting hundreds of `medium` findings still exits 0 — that is the gate working, not the tool ignoring them. `--min-severity` filters *before* the gate, so hiding a severity also stops it ever failing a build.

**Exit status 2 means a file could not be parsed, and it overrides `--fail-on never`.** An unreadable file produces no findings for the same reason an empty one does, so letting it pass would report a green check on code the reviewer never looked at. Unparsed files are listed on stderr and in the JSON under `files_unreadable`, and `files_scanned` counts only what was actually read.

It parses `.TcPOU`/`.TcDUT`/`.TcGVL`/`.TcIO` and plain `.st`, walking **every** declaration/implementation pair — POU body, methods, property getters and setters. That matters: a top-level-only parse misses about 84% of the code in an OOP project.

Findings carry a rule id you can cite in a review — `CP8`, `X1`, `E3`. The `CP`/`N`/`C`/`L`/`E` ids are PLCopen Coding Guidelines rules and carry that document's own severity; the `X` ids are this skill's own, for what that catalogue does not cover — the failure modes specific to a scanned task, plus `X9` for the PLCopen *behaviour model* contract, which is standardised in a different document. `plcopen-rules.md` is the full catalogue.

**What it does not see.** Most rules judge one file at a time (`CP2`, `CP7` and `CP12` look
across the scanned tree), and none has the task configuration or the library source, so anything that depends on which task runs a POU — two tasks writing one
variable, a lock that is never released — is out of its reach (`twincat/tasks-and-exceptions.md`).
An LD or FBD body is read only as a list of the names it mentions: a variable wired there counts
as used, but no rule judges the network's logic.

CP8 does not report a float compared with a copy latched from it (`fTarget := fSetpoint;` …
`fTarget <> fSetpoint`). That is change detection, where exact is right, and half of CP8's high
findings on one real project were this shape. The same text is also a settle check on a measured
value (`fLast := fWeight;` … `fWeight = fLast`), where exact is wrong, and the reviewer cannot
tell the two apart. On the 2,189-file public corpus the exemption skips 4 comparisons, all
correctly; the settle check is judged by hand (Rule 6 in `cyclic-execution-rules.md`).

## `scripts/tcpou.py`

Editing a `.TcPOU` as plain text is how you corrupt a project. Every subcommand:

```bash
py -3 scripts/tcpou.py show     <file>                                   # parts + encoding
py -3 scripts/tcpou.py get      <file> --part impl [--out body.st]       # print or write one part
py -3 scripts/tcpou.py pins     <file> [--pin REGEX] [--box REGEX]       # FBD/LD box wiring
py -3 scripts/tcpou.py set      <file> --part impl --from-file body.st   # replace one part
py -3 scripts/tcpou.py new      --type fb --name FB_Filling --dir POUs/  # scaffold
py -3 scripts/tcpou.py add-method   <file> --name Reset [--returns BOOL] # append an empty METHOD
py -3 scripts/tcpou.py add-property <file> --name Speed --type LREAL     # append a PROPERTY
py -3 scripts/tcpou.py register <PLC.plcproj> <file>...                  # make it compile
py -3 scripts/tcpou.py reguid   <file>...                                # re-stamp Ids
py -3 scripts/tcpou.py check    <file>...                                # validate
py -3 scripts/tcpou.py code-equal <file|dir>... [--ref REV | --against FILE] # comments-only?
```

- `new` takes a **`--name`, not a path**, and picks the extension itself (`.TcPOU`/`.TcDUT`/`.TcGVL`). `--type` is one of `fb`, `prg`, `fun`, `dut`, `gvl`; `fb` also takes `--extends`, `--implements` and `--shape`.
- **`--shape` picks which interface family the FB gets:** `execute` (the default) declares `bExecute`/`bBusy`/`bDone`, `enable` declares `bEnable`/`bValid`, and `cyclic` declares no command interface at all. Choose the one the block actually is — `Execute` pairs with `Done`, `Enable` pairs with `Valid`, and mixing the two is what rule `X9` reports. `references/behaviour-model.md` is the decision. An FB that **inherits** its command interface from a framework base — the common case in a module-based project — fits none of the three on its own: use `--shape cyclic --extends FB_YourBase`, which gives the `EXTENDS` and adds no pins of its own to clash with the base's.
- `set` reads stdin when `--from-file` is omitted. **From Windows PowerShell 5.1, move a part with `get --out body.st` and `set --from-file body.st`, never with `>` or a pipe.** `>` is `Out-File`: it decodes the script's UTF-8 through the console code page before writing UTF-16, so `²` lands in the file as `┬▓` and no reader can repair it. A pipe (`Get-Content body.st | set`) re-encodes each character to the console code page: a BOM-less file arrives with `²` as `??`, with `-Encoding UTF8` as `?`; lost either way. (cmd.exe's `>` and `type |` are fine.) `--from-file` and stdin take UTF-8 with or without a BOM and UTF-16 with one; anything else is refused in one line. One trailing line break more than the part already has, which a pipe or an editor appends, is dropped so a round trip leaves no diff. Files and output are UTF-8 whatever the console's code page.
- `add-method` and `add-property` append an empty member to a POU or interface; fill its parts with `set`. `--access` takes `PUBLIC`, `PRIVATE`, `PROTECTED` or `INTERNAL` (none reads as `PUBLIC`); `add-property --no-set` makes it read-only.
- Part keys come from `show`: `decl`, `impl`, `Reset:impl`, `ActualValue.Get:impl`.
- **`pins` before concluding a signal is unused or unwired in an FBD or LD caller.** Which variable feeds which pin of a box is stored in the network XML, so a text search for `ibEmpty :=` finds nothing there. `pins` prints every box's inputs (`<-`, with operators as `OR(a, b)`, a negated operand as `NOT x`, an empty pin as `(unwired)` and, in LD, the rung input as `(rung: left rail, TRUE)`) and its wired outputs (`->`), each box tagged with the method its network lives in, `[MotionCycle]`. Coil rungs and conditional RETURN rungs have no box and are listed as `(coil) var <- AND(a, NOT b)` and `(return) <- NOT x`; `--pin var` finds the coil. It is read-only; the layout it reads was checked on 4024 LD networks and one FBD network drawn in XAE, against XAE's PLCopen export and in the editor. CFC is not supported: on a `<CFC>` body `pins` refuses with exit 2 rather than print an empty list, and nothing here reads a CFC box.
- **Claim "comments only" with `code-equal`, not by eye.** It compares every source part with the same part at `--ref` (default `HEAD`) or in `--against` another file, after dropping comments and insignificant whitespace; string literals count as code. Exit 0 = IDENTICAL, 1 = the code changed (it prints the first difference per part), 2 = nothing to compare with. A directory stands for every `.TcPOU`/`.TcDUT`/`.TcGVL`/`.TcIO` under it, so a whole project is one command, with a count of each verdict at the end. It reads the CDATA source only, not the XML around it.

**Run `show` before `get`/`set` rather than guessing a part key.** A wrong key exits 1 and prints the real ones — but if you then verify your own edit by hashing the file, a `set` that never ran looks exactly like a `set` that changed nothing. Check the exit status, not just the bytes.

**A new file that is not registered in the `.plcproj` silently does not compile.** `tcpou.py register` is not optional; it is idempotent, so running it twice is safe.

**`set`, `add-method`, `add-property`, `register` and `reguid` refuse a project an XAE has open**, exit 1, and change nothing. They look for a `<project>.project.~u` lock file that XAE rewrote in the last two minutes, in the file's folder and each one above it up to the folder holding the `.sln`. A write there makes XAE ask to reload, and can lose edits it holds unsaved (`twincat/xae-automation.md`). Edit through that XAE with `xae_edit.ps1` instead. `--allow-open` writes anyway; use it only when the user has said to expect the reload prompt. `show`, `get`, `check`, `pins` and `code-equal` only read, and never refuse.

## `scripts/xae_edit.ps1`

Edits, saves and builds through the XAE the user has open, so XAE never asks to reload. Windows with
XAE only, in Windows PowerShell 5.1 (`powershell.exe`, not `pwsh`) at the same elevation as XAE.
Why it works and what was measured is in `twincat/xae-automation.md`.

```powershell
# each line runs as: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_edit.ps1 <command> ...
xae_edit.ps1 list                                                         # every XAE: PID, solution, dialogs
xae_edit.ps1 show       '<TreePath>' -Solution x.sln                      # type, language, file, saved, children
xae_edit.ps1 get        '<TreePath>' -Solution x.sln -Part impl -Out body.st
xae_edit.ps1 set        '<TreePath>' -Solution x.sln -Part impl -FromFile body.st
xae_edit.ps1 add-method '<PouPath>'  -Solution x.sln -Name M_Reset [-FromDecl d.st] [-FromImpl i.st]
xae_edit.ps1 add-pou    '<Folder>'   -Solution x.sln -Name FB_Pump [-Lang st|ld]
xae_edit.ps1 save       '<TreePath>' -Solution x.sln
xae_edit.ps1 build                   -Solution x.sln [-SaveUserEdits] [-PublicAssemblies <dir>]
```

**Tree paths** are XAE's, joined with `^`: `TIPC^PLC1^PLC1 Project^POUs^FB_X` for a POU,
`…^FB_X^M_Reset` for one of its methods. Quote them: they contain spaces. A path that does not
exist exits 1 and prints what its nearest existing parent holds; `show` with no path lists `TIPC`.

| Command | Does | Refuses |
|---|---|---|
| `list` | Every XAE in the Running Object Table, with its solution or the dialog it shows; and any XAE process missing from the table, which runs at another elevation | — |
| `show` | Item type (604 function block, 609 method), language (1 ST, 6 LD), the file it lives in, whether that file is saved and by whom it was edited, and its children | — |
| `get` | Writes the part's text, as XAE holds it, to `-Out` (UTF-8, no BOM, LF). `-Part` defaults to `impl`. An LD/CFC body comes out as its XML | — |
| `set` | Replaces `-Part decl` or `impl` from `-FromFile` in XAE's memory, then reads it back | an LD/FBD/CFC/SFC/IL body; a file of XML; a POU with unsaved edits it did not make |
| `add-method` | Creates the method in that POU, then sets its declaration and body when given | a name the POU already has; a POU with unsaved edits it did not make |
| `add-pou` | Creates a function block in that folder. XAE writes the `.TcPOU` and registers it in the `.plcproj` at once: no `register` needed | a name the folder already has |
| `save` | Saves the file the path lives in, so a method saves its POU. Never Save All | a POU with unsaved edits it did not make |
| `build` | Lists what the build will save, builds in that XAE, prints the Build pane and the compiler entries of the Error List | when an unsaved PLC object holds edits it did not make |

- **Input files** (`-FromFile`, `-FromDecl`, `-FromImpl`) are UTF-8 with or without a BOM, or UTF-16
  with one; anything else is refused rather than written into the POU as U+FFFD. `get` takes `-Out`
  and never prints to the console, whose code page loses characters such as `²`.
- **A `set` is not on disk until `save`.** `st_review.py` and `git diff` read the disk, so save
  before reviewing. Prefer `get -Out` to read code the user may have changed in XAE: the file can be
  older than what XAE holds.
- **`-Force`** lets `set`, `add-method` and `save` go ahead on a POU that holds someone else's
  unsaved edits: `set` replaces the whole part, so their edits in that part are lost, and `save`
  writes all of them to disk. **`-SaveUserEdits`** lets `build` save them. Both are for when the
  user has said so. Without them the tool tells its own unsaved edits from the user's by a fingerprint of the POU
  it takes after each write, kept in `%TEMP%\twincat-st-xae_edit-<hash>.txt` and void once XAE
  restarts.
- **`add-pou` makes function blocks only**, in ST or LD. Programs, functions, properties, DUTs and
  GVLs take type codes nobody has verified yet; make those in XAE, or with `tcpou.py` while XAE is
  closed. To give a new block `EXTENDS`, `set` its declaration.
- **`build` needs `envdte.dll`** from the XAE's own `PublicAssemblies` folder, like `xae_build.ps1`:
  pass `-PublicAssemblies` when XAE is not installed in the default place. It rewrites `.tmc`,
  `.xti` and `_CompileInfo` like any build, without a prompt. Quote its `Build complete -- N errors,
  M warnings` line as the evidence.

**Exit code:** 0 = done; 1 = failed, refused, a readback that differs from what was set, or a build
with a failed project; 2 = could not run: no XAE holds the solution, several do, XAE shows a dialog
or did not answer for 30 s, or the wrong PowerShell. On exit 2 because of a dialog, ask the user to
answer it; never click it from a script.
