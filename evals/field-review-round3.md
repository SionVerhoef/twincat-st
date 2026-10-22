# Field review -- round 3 (v0.4 tools)

Round 3 ran the v0.4 tools on the TwinCAT PC: TwinCAT 3.1.4024.55, Windows 10 22H2, Python
3.12.10, Windows PowerShell 5.1, skill at commit `883fc6a` (PR #34). The real project is
Project_A again, a packaging machine on TwinCAT 3.1.4024; its names are replaced by stand-ins.
A scratch TcUnit solution was recreated headless for the build checks. `PYTHONUTF8` was unset and
`PYTHONIOENCODING` unset for the user and machine; the agent's own shell inherits
`utf-8:surrogateescape` and code page 65001 from its host app, so every run cleared both and
used `chcp 437`, confirmed by an echo in each run.

Every fix below has a test in `tests/run_tests.py`. **None has been re-run in XAE yet**; that is
round 4, listed at the end.

| Check | Result | Fix |
|---|---|---|
| 1 `run_tests.py` | pass from the clone (90 ok); **fail from the installed copy**: `--ref HEAD` needs a git checkout | the test makes its own repository |
| 2 `get`/`set` with `²` | cmd.exe: `>` and `type \|` round-trip clean. PowerShell 5.1: `>` writes UTF-16LE with `²` already mangled to `┬▓`, and `set --from-file` **crashes** in a `UnicodeDecodeError` traceback; a pipe turns `²` into `??` (`?` with `-Encoding UTF8`) and adds a line before `]]>` | decode by BOM; `get --out`; drop the one trailing line break a pipe adds; `SKILL.md` says `get --out` + `set --from-file` from PowerShell |
| 3 `pins` vs XAE's PLCopen export | 6 LD callers, 56 boxes, 1,066 pins: operands and order match. Mismatches: the rung input printed `(unwired)` on 48 boxes; 6 negations dropped. Not listed at all: method context, 1 coil rung, 18 RETURN rungs. **No FBD or CFC POU in the project**: all 43 graphical POUs are LD (`<NWL>`, `DefaultViewMode "Ld"`) | rail input, `NOT x`, `[Method]` header, `(coil)` and `(return)` lines; `<CFC>` body exits 2 |
| 4 `code-equal` | comments reworded / re-indent: IDENTICAL; value, `//` in a string, text after `//` in a string, add-method: DIFFERENT (the old field script passed the string case). `--against`: IDENTICAL. 1,352 unmodified files vs `HEAD`: **1,351 IDENTICAL, 1 false DIFFERENT** (`core.autocrlf=true` + a multi-line string literal). 511 KB POU 0.13 s; 1,352 files about 40 s | compare line endings as LF inside string literals too |
| 5 `xae_build.ps1` | scratch solution: exit 0, `Build complete -- 0 errors, 0 warnings`, 18 s; `-TreePath` lists the method `add-method` wrote; a broken line exits 1 with `Build complete -- 2 errors` (one of the two Error List entries has no file name); `-Rebuild` ok; wrong `-PublicAssemblies` exits 1 with the right message wrapped in a `Write-Error` record. **Same solution open in XAE**: build passes, that XAE keeps running but asks to reload the `.xti`; Yes reloads cleanly. A different solution open: untouched across 7 builds. Project_A: exit 0, 44.9 s, `.tmc`, `.xti` (208 lines without compile state) and the Measurement `.vsm` rewritten | header, doc and a lock-file warning; `[Console]::Error.WriteLine` |
| 6 agent behaviour | B1 pass: said what a build rewrites, ran the script, quoted the `Build complete` line, restored. B2 pass: no activation attempt, handed over the steps with the boot-folder backup; one wrong line, "TcUnit results on the Messages tab" | the TcUnit-as-Errors line repeated in `xae-automation.md` |

What a build rewrites, measured in check 5 and now in `references/twincat/xae-automation.md`: the
first build of a fresh project rewrites the `.plcproj` and creates `_Boot/`; a rebuild adds a new
`_CompileInfo/<guid>.compileinfo` and leaves the old one; an incremental build with no source
change rewrites `_CompileInfo`, `_Boot` and the `.xti` but not the `.tmc`; the `.vsm` changes as
soon as XAE opens the solution.

The RunEmptyDone diagnosis from round 2 holds up: before the old commit `pins` shows
`out obEmpty -> <machine>.bRunEmptyDone`, at `HEAD` `out obEmpty -> obEmpty`, and the rewired
inputs show their new source.

## Shapes seen, and not seen

From the LD networks of Project_A (names replaced; the fixture `tests/fixtures/tcpou/FB_LdCaller.TcPOU`
is built from these):

- Every graphical POU is `<Implementation><NWL>` with `<v n="DefaultViewMode">"Ld"</v>`; the POU
  body is empty and the networks live in three methods per POU.
- An instance box's `InputItems[0]` is `<o t="BoxTreeTerminator"><n n="Input" />…`: the rung
  input, which XAE's export connects to the left power rail. A terminator occurred only at
  index 0. Every other unwired input is a `BoxTreeOperand` whose `Operand` is `""`. An unwired
  output is a bare `<n />`.
- A negated operand carries `<o n="Flags" t="Flags"><v n="Flags">1</v></o>`; XAE exports it
  `negated="true"` on the contact and on the pin. Every `Flags=1` operand matched a negation and
  no `Flags=0` operand was negated.
- A conditional RETURN rung is a `BoxTreeAssign` whose one output operand is `"???"` with
  `Flags` 8 and whose `RValue` is the condition; in Project_A always a single negated operand.
  Reading `???`/8 as RETURN is inferred from the export and is marked so in `tcpou.py`.
- A coil rung is a `BoxTreeAssign` whose output operand names the variable (`Flags` 0) and whose
  `RValue` is nested operator boxes, here `AND(OR(a, b, c), NOT d)`.
- An empty CFC body made by XAE 4024 is `<Implementation><CFC>`: an `XmlArchive` whose root is
  `CFCImplementationObject` with `<o n="Items" t="CFCItemList"><l2 n="InnerList"/>`, a
  `RoutingPathTable` and the canvas size. How a box and its pins sit inside `InnerList` is
  unknown: nobody has drawn one yet.

Not present in the project, so untested: an FB output wired straight into another box, `EN`/`ENO`,
negated outputs, edge contacts, jumps, any FBD network.

## Round 4 (to run on the TwinCAT PC)

1. `run_tests.py` from the clone and from the installed copy, without `PYTHONUTF8` or
   `PYTHONIOENCODING`.
2. PowerShell 5.1 round trip with `get --out` and `set --from-file` on a POU with `²`: empty
   diff. A UTF-16 file from `>`: a clean one-line error or a correct round trip. A pipe: no extra
   line before `]]>`.
3. `pins` against XAE's PLCopen export (`ITcPlcIECProject.PlcOpenExport`) on the same six LD
   callers: expect 0 mismatches. Round 3 had 48 rung inputs and 6 negations. Coil and RETURN
   rungs should now be listed.
4. A human draws a small CFC POU in the scratch project (an FB box with one wired input, an
   operator input, one unwired input, one output) so the CFC box storage can be described.
5. `code-equal` over all 1,352 Project_A source files: 0 DIFFERENT.
6. `xae_build.ps1` with the solution open in XAE: the lock-file warning appears, and the doc's
   advice matches what XAE does.
