# Fixture project

A small TwinCAT 3 project the file-on-disk evals run against. It exists so the agent
has to do what an engineer actually does — find the objects, read the XML, descend into
methods, edit in place and keep the `.plcproj` correct — rather than answer a question
about a snippet pasted into chat.

`evals/prepare_run.py` copies this into every cell of a run, so each agent gets a
pristine copy and the grader can diff against this original.

## Deliberate properties

**House style differs from the skill's documented default.** BOOLs here are `x`-prefixed
(`ixStart`, `qxHomed`), not `b`-prefixed, and inputs/outputs carry `i`/`q`. `SKILL.md`
says to match the surrounding project even where it differs from
`references/naming-conventions.md`; `style-match` measures whether that actually happens.

**The defects are inside a `METHOD`, not the POU body.** `FB_Filler`'s body is clean;
`FB_Filler.DoseComplete` holds a scan-blocking `WHILE`, a `TON` preset written as a bare
`250`, and an `=` comparison on two `LREAL`s. A top-level-only read reports this project
clean, which is the 84%-of-an-OOP-project claim the skill makes, turned into a test.

**Line endings vary.** `FB_Homing.TcPOU` is CRLF, the rest are LF, and all carry a BOM —
close to the measured corpus (97% BOM, 19% CRLF). An edit must preserve whatever the file
it touched already used.

**`FB_Homing` step 10 waits on `ixHomeSensor` with no timeout.** That is a design gap no
pattern checker can see, which is why a human asks for it in `edit-existing-pou`.

## Known baseline

`scripts/st_review.py evals/fixture-project` reports exactly three high-severity findings,
all in `FB_Filler.DoseComplete` — X1, X2 and CP8. Any other finding in a graded run is
something the agent introduced.
