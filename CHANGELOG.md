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

### Validation

- Reviewer swept across **440 real `.TcPOU` files**; four false-positive classes found and
  fixed, two contested rules moved behind `--pedantic`.
- `evals/` holds five prompts and a mechanical grader. Iteration 1 scored 31/31 with the
  skill against 26/31 baseline — see `evals/results-iteration-1.md`, including the two evals
  that did not discriminate at all.

### Known gaps

- **Nothing here has been compiled.** No TwinCAT toolchain existed in the environment this
  was built in, so no template has been loaded into XAE. `SKILL.md` rule 3 makes the skill
  declare that gap rather than paper over it.
- `references/codesys.md` is marked untested and says so.
- `examples/` teaches *a* house style, not yours. Adding real project code is the single
  highest-value improvement available — see `examples/README.md`.
