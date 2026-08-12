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

- `scripts/st_review.py` — 19 rules, PLCopen-keyed, standard library only. Walks **every**
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

### Validation

- `tests/run_tests.py`, in CI: every rule must still fire on a defective fixture, the
  negative fixture must stay silent, `X6` must separate its two cases by severity, and
  `tcpou.py` must round trip byte-exact across BOM, LF, CRLF and mixed-ending files.
  Verified by mutation — reverting any of the four fixes above fails it.
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
