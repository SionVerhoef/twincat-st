# Changelog

## Unreleased

First public version, extracted from a private repository.

### Skill

- `SKILL.md` leads with the **execution model** rather than syntax: the five shapes, the
  three hard rules (no safety logic, no writes to a live machine, no unverified compile
  claims), and a verification ladder that names what was actually proven.
- Thirteen references, loaded on demand rather than up front.
  `references/cyclic-execution-rules.md` is the core; `references/plcopen-rules.md` carries
  the 64-rule PLCopen catalogue with severities.
- Scope is the CODESYS V3 dialect family — TwinCAT 3 primary, CODESYS secondary. Siemens SCL,
  Rockwell ST and OpenPLC/matiec are explicitly refused rather than answered badly.

### Tools

- `scripts/st_review.py` — 20 rules, PLCopen-keyed, standard library only. Walks **every**
  declaration/implementation pair, including methods and property accessors; a top-level-only
  parse misses roughly 84% of the code in an OOP project. Exits 1 at or above `--fail-on`
  (default `high`) so it can gate CI.
- `scripts/tcpou.py` — reads and edits `.TcPOU` files without disturbing GUIDs, `<LineIds>`,
  the BOM or line endings. `new` scaffolds, `reguid` re-stamps after a copy, `register` adds
  the file to the `.plcproj` — which is not optional, since an unregistered file silently
  does not compile.
- `.gitattributes` marks TwinCAT object files `-text`, so they round-trip byte-exact
  regardless of `core.autocrlf`.

### Examples and templates

- Ten unmodified source files from three permissively-licensed projects (MIT, MIT, BSD-2),
  each folder carrying its upstream `LICENSE` and a `NOTES.md`. See `ATTRIBUTIONS.md`.
- Known-good skeletons for a sequence FB, a state enum and a TcUnit suite. They pass the
  skill's own reviewer.

### Fixed after the first external test

An independent test on Windows against a 1352-file TwinCAT project, plus a review of the
findings it produced.

- **`CP8`/`CP28` missed the assignment form.** `IF fActual = fTarget` was reported but
  `bAtTarget := (fActual = fTarget);` was not — a whole-line skip on `:=` discarded the
  exact defect the skill leads with. Now excluded per operator instead of per line.
- **`X4` named the wrong token and ignored guards that were there.** It read `x / TO_REAL(n)`
  as dividing by `TO_REAL`, and reported `stCfg.nDiv` and `aVals[1]` as unguarded while the
  line above them read `IF stCfg.nDiv <> 0`. Guards now match the whole divisor expression,
  a conversion call is guarded through its argument, and `IF n = 0 THEN RETURN` counts.
- **`X6` ranked a METHOD parameter like an unwired FB input.** A method call site must bind
  every input, so that case now reports `low`. It is not dropped — a caller can still pass
  its own unassigned reference through. Roughly 44% of `X6` findings on real OOP code.
- **`tcpou.py` rewrote every line ending in a file whose endings were mixed.** One stray
  CRLF in an LF file became 152 after a no-op edit. The text is no longer normalised on
  read; only the incoming payload is matched to the file's dominant ending.
- **`tcpou.py` raised a stack trace on a missing path** in all six subcommands. It now
  reports the same way `st_review.py` does.
- **Docs.** `SKILL.md` gained the full `tcpou.py` command table (`new`'s signature was
  documented nowhere), the `--fail-on`/`--min-severity`/`--rules` flags, the default gate,
  and advice to scan the application folder rather than the whole `.plcproj`. The README
  gained Windows install and invocation instructions: `python3` cannot work there, since
  the python.org installer creates no `python3.exe` and the Microsoft Store alias stub
  answers instead.

### Fixed after the second external test

A second independent test on Windows, against the same project grown to 1374 files. It
confirmed all six round-1 defects fixed, and found two more.

- **`tcpou.py new --type fb` scaffolded a PLCopen contract violation.** It emitted `bEnable`
  paired with `bDone` — the level-controlled trigger with the edge-triggered completion
  output, the exact mix `references/behaviour-model.md` names as the mistake — and omitted
  `bBusy`. So the scaffolder disagreed with both that document and
  `templates/FB_Sequence.TcPOU`, which gets it right. `new` is where every FB written with
  this skill starts, and an agent has no reason to doubt a skeleton the skill produced.
  `--shape` now picks the family: `execute` (the default, matching the template) gives
  `bExecute`/`bBusy`/`bDone`, `enable` gives `bEnable`/`bValid`, `cyclic` gives neither.
- **Nothing reviewed what the scaffolder produced.** Rule **`X9`** now reports an FB that
  pairs `Enable` with `Done` or `Execute` with `Valid`, and `tests/run_tests.py` scaffolds
  each shape and reviews it, so the two tools check each other instead of drifting apart.
  `X9` stays quiet when an FB carries *both* triggers — a command block behind an enable
  gate is a real design, and the text cannot prove otherwise. It fired zero times on
  `examples/` and `templates/`, and zero times on the tester's 111 application files —
  the second of those turned out to mean nothing, for the reason the next section gives.
- **The Windows fix was in the prose, not in the commands.** `SKILL.md` said "on Windows use
  `py -3`" beside code blocks that all still read `python3`, and an agent scanning for a
  command copies the block, not the sentence next to it — which is what cost the tester
  their first run. Every block in `SKILL.md` and the README is now written `py -3`, with the
  Linux and macOS form stated once in prose.

The tester also reported that the round-1 `CP8` fix immediately paid for itself: on the real
project it turned up an `LREAL` measured servo position compared with `=` against a computed
target, a status bit that can essentially never go true. That was invisible before the fix.

### Fixed after the third external test

A third independent test on Windows, against the same project. It confirmed `--shape` and
`X9` working on every scaffolded shape, and found that `X9` could not see the project at all.

- **`X9`'s pin matchers missed every IEC direction prefix.** `^[bx]?Enable$` cannot match
  `ibEnable`, and a direction letter ahead of the type letter is mainstream Beckhoff house
  style rather than one site's quirk. Measured on the tester's 1374-file project: 108 function
  blocks carry an `Enable` pin and 86 carry `Done`, and the rule matched none of them — it
  reported a clean codebase it had never actually looked at. The four `PIN_*` patterns now
  allow an optional direction letter (`^[ioq]?[bx]?...$`), which fires 18 times there with no
  false positives. The anchoring stays, and is now the point: a substring match fires 31 times
  on the same project and 13 of those are wrong, because `obPurgeCycleDone` and
  `ibDryRunEnabled` name the completion of one specific operation rather than a PLCopen
  command pin. Both halves are fixtures now — a prefixed violation that must fire, a prefixed
  *correct* pairing that must not, and a set of named completions that must not.

  A rule that has stopped matching and a rule with nothing to report produce identical output.
  The tester caught this only by printing the population scanned next to the findings count.

### Fixed after the automated PR review

Twelve defects raised on the rebuild PR — four in its review comments, eight more folded
behind its "suppressed comments" summary — each verified here against a repro before being
fixed. Every code fix has a regression test, and each test was mutation-checked by
reverting the fix.

Four of them made a rule report the opposite of the truth, and three of those were in
rules the skill sells itself on:

- **`X5` treated a null *test* as a null *guard*.** Any comparison against zero in the
  preceding lines was accepted as proof, so `IF p = 0 THEN Log(); END_IF; x := p^;` — which
  notices the null case and then lets it through — scanned clean. It now takes only the two
  shapes that actually stop the null path reaching the dereference: `IF p <> 0 THEN`, or a
  null branch that `RETURN`s, `EXIT`s or `CONTINUE`s. `X4` already drew this distinction;
  `X5` had collapsed both operators into one pattern.
- **An unparseable file scanned green.** A parse error was turned into an empty unit, so the
  file produced no findings and the run exited 0 — the CI gate passing on code it never
  read. Unreadable files are now listed on stderr and in the JSON, excluded from
  `files_scanned`, and exit **2**, which `--fail-on never` cannot suppress: "could not
  check" is a tool failure, not a clean result.
- **`reguid` reported success after regenerating nothing.** The documented workflow is copy
  the template, then `reguid` the copy, so `ok (0 GUIDs regenerated)` said the identity was
  refreshed when it was not — leaving the copy colliding with the template on the same `Id`,
  which is exactly the conflict the command exists to prevent. Zero replacements now fails
  and the file is left untouched.
- **The shipped TcUnit suite contained a test that could only fail.** `FB_Sequence` hardcoded
  both step conditions to `IF TRUE`, so the timeout fixture always reached `bDone` and
  `TestTimeoutRaisesError` always took its `AssertTrue(FALSE)` branch. Found while
  verifying: it also asserted `nErrorID = 16#8001`, while the block raises `16#8101` — wrong
  even had the path been reachable. The step conditions are now inputs, which is what lets a
  test hold a step open and watch it fault, and the suite drives its two fixtures
  differently so both the completion and the timeout path are genuinely exercised.
- **`<Action>` bodies were never reviewed, and their variables reported as unused.**
  `tcpou.py` has always recognised `Action`; `parse_xml` walked every container except
  that one. The gap cut both ways — a `CP8` float comparison and an `X4` unguarded
  division inside an action went unreported, while all five declarations the action used
  came back as `CP24` unused, because from the reviewer's side nothing referenced them.
- **`X2` reported the correct `udiTimeOut := 500` as high.** It matched pin *names* that
  sound like timeouts. But `udiTimeOut` is PLCopen's UDINT millisecond pin — documented
  as such in this skill's own `references/behaviour-model.md` — so a number is right
  there and `T#500MS` would be the type error. It now keys on things that really are
  TIME: `PT`, a `t`-prefixed pin, or a variable the scope declares as TIME.
- **`X3` accepted a nested `IF`'s `ELSE` as the `CASE`'s fallback.** Nesting was not
  tracked, and since almost every real state branch contains an `IF/ELSE`, the rule was
  close to inert on the state machines it exists to check.
- **`X7` was satisfied by a `bError` output.** It searched for any identifier containing
  Error/Fault/Alarm/Abort anywhere in the file, which nearly every FB supplies, so it
  missed exactly the defect it claims to detect. It now looks for an error *state*: a
  label that says so, or a step that raises the fault flag — the second signal is not
  optional, because a machine that numbers its steps (`99: qxError := TRUE;`) has no room
  to say "error" in a label, and matching label text alone reported one such machine in
  `evals/fixture-project` as having no error state at all.

One more came from a human read of the PR rather than the bot, and it is the worst of
the set because it is the template every FB written with this skill starts from:

- **`FB_Sequence` called its step timer from inside the `CASE` branches** — the shape
  `references/cyclic-execution-rules.md` Rule 5 prints under a `// WRONG` comment, in the
  skill's own flagship template. Rule 5 adds that sharing one timer instance across
  several states is a bug, and `fbStepTimer` was shared by `Step1` and `Step2`; Rule 2
  says the call site is unconditional and the input is the control. It *worked*, because
  `M_EnterStep` reset the timer on every transition — but a reader copying the shape
  gets no such guarantee, and swapping the `TON` for a `TOF` breaks it outright, since a
  `TOF` must keep being called after `IN` falls. The edge detector and the timer are now
  called once, unconditionally, above the `CASE`, with `IN` held low for the single scan
  on which the state changes — so the re-arm is structural rather than something a future
  transition has to remember. `M_EnterStep` became a bare assignment and is gone.
  Nothing in `st_review.py` looks for this shape, so `tests/run_tests.py` now asserts the
  timer has exactly one call site and that it sits above the `CASE`.

And four documents that contradicted the code or each other:

- `references/testing-tcunit.md` stated flatly that each test method declares its own
  fixtures — which recreates the reset-every-scan bug fixed above, and contradicted its
  own multi-cycle section further down. It now says which kind of test each scope suits.
- `examples/tcmatrix-tests/NOTES.md` still described the `FOR`-loop-of-calls test pattern
  that was removed for not working.
- `examples/packml-vffs/NOTES.md` said there is no constructor in ST, while
  `references/twincat.md` documents `FB_init` as TwinCAT's. The real reason that example
  uses an init state machine is that its work spans scans, which `FB_init` cannot.
- `examples/README.md` gave commands no working directory could run: `../scripts/...`
  paired with globs beginning `examples/`. Its blocks, and those in `templates/README.md`,
  are now `py -3` from the repository root like the rest of the skill — the round-2 fix
  had reached `SKILL.md` and the top-level README but not these two.

### Validation

- `tests/run_tests.py`, in CI: every rule must still fire on a defective fixture, the
  negative fixture must stay silent, `X6` must separate its two cases by severity, `X9` must
  catch both directions of a mixed behaviour model and see through a direction prefix,
  what `tcpou.py` scaffolds must pass the
  reviewer, and `tcpou.py` must round trip byte-exact across BOM, LF, CRLF and mixed-ending
  files. Verified by mutation — reverting any of the fixes above fails it, including each
  branch of `X9` separately. One fixture per branch is deliberate: with only one, a typo in
  the other detects nothing and the "every rule fires" check stays green on the half that
  works.
- Reviewer swept across **440 real `.TcPOU` files**; four false-positive classes found and
  fixed, two contested rules moved behind `--pedantic`.
- `evals/` **rebuilt for iteration 2**, because iteration 1's 31/31-against-26/31 flattered
  the skill. Three things were wrong with it and all three are fixed:
  - *The tasks were too easy.* Every prompt pasted self-contained ST into the chat. Most
    evals now hand the agent `evals/fixture-project/` — a real project directory whose
    defects sit inside a `METHOD`, invisible to a top-level read — and grade the files it
    leaves behind: did the GUIDs survive, is the new object registered in the `.plcproj`,
    did the CRLF file stay CRLF.
  - *The checks were keyword proxies.* "Error state reachable" passed on the word `error`
    appearing anywhere. Artifact checks are ground truth instead; a `.TcPOU` either parses
    or it does not.
  - *A non-discriminating guardrail was in the headline number.* `safety-boundary` scored
    6/6 in both arms; it is now reported separately, as pass/fail.
  Each cell runs three times and reports a mean with its range, replacing iteration 1's n=1.
- `evals/selftest.py`, in CI: the grader is itself graded. A synthetic gold run must score
  full marks and a null run must score zero. Its first execution caught seven checks in
  `edit-existing-pou` that passed for an agent which had not touched the file — "GUIDs
  unchanged" is trivially true when nothing happened. All such checks are now gated on
  evidence the agent acted.

### Known gaps

- **Nothing here has been compiled.** No TwinCAT toolchain existed in the environment this
  was built in, so no template has been loaded into XAE. `SKILL.md` rule 3 makes the skill
  declare that gap rather than paper over it.
- `references/codesys.md` is marked untested and says so.
- `examples/` teaches *a* house style, not yours. Adding real project code is the single
  highest-value improvement available — see `examples/README.md`.
