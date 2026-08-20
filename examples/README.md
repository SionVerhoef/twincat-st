# Examples

Real, working Structured Text to pattern-match against. Prose conventions are a weak signal; a model that has read three real function blocks writes code that looks like it belongs in a real codebase.

Ten files across three projects, each folder carrying its upstream `LICENSE` and a `NOTES.md` explaining what to take from it — and where it disagrees with this skill.

| Folder | Source | Licence | Shows |
|---|---|---|---|
| [`packml-vffs/`](packml-vffs/) | [Beckhoff-USA-Community/PackML_PLC_Example](https://github.com/Beckhoff-USA-Community/PackML_PLC_Example) | MIT | A real packaging machine: `MAIN` as pure wiring, an `ABSTRACT` module base with init and alarms, a device FB implementing an interface, direct I/O mapping, the config/status/command DUT split |
| [`tcmatrix-tests/`](tcmatrix-tests/) | [BurksEngineering/TcMatrix](https://github.com/BurksEngineering/TcMatrix) | MIT | TcUnit structure: the `TcUnit.RUN()` runner, `When…Expect…` test naming, arrange/act/assert sections, testing the error path |
| [`design-patterns-state/`](design-patterns-state/) | [0w8States/PLC-Design-Patterns](https://github.com/0w8States/PLC-Design-Patterns) | BSD-2 | The State pattern as the OOP alternative to `CASE eState OF`, with an honest when-to-use-which table. Plus a minimal `qualified_only` GVL |

**Read the `NOTES.md` in each folder, not just the code.** The notes carry the reasoning — including the places where these projects use three *different* naming conventions, none of them the one in `references/naming-conventions.md`. That is the point, not an oversight: the rule is *the project you are editing wins*, and these files are what that looks like.

## Why only these three

These files ship inside the skill, so the licence has to permit redistribution. That rules out most of the best material: vendor samples and standards are copyrighted, and copyleft code would relicense the whole skill. Beckhoff's own OOP Extended Sample is arguably the strongest reference architecture available and it cannot ship here — you can read it, and `references/patterns.md` describes what it does, but the files stay where they are.

What is left is the permissively-licensed end of the ecosystem, which is where these three come from. Licences were read from each repository's actual `LICENSE` file, not from a GitHub badge. See `../ATTRIBUTIONS.md`.

## The gap these do not fill

**None of this is your code.** It is well-chosen open-source code, and it is the best that can be legally shipped, but it teaches *a* house style rather than *your* house style. Dropping in real project code remains the single highest-value improvement available to this skill.

Good candidates, in rough order of value:

1. A **device FB** — one physical thing, showing how you handle enable, feedback and faults
2. A **sequence FB** — a real multi-step process, showing how you structure states and timeouts
3. Your **error handling** — how error IDs are allocated, reported and reset
4. A **`MAIN`** — how you wire the top level, and in what order
5. A **GVL** — how globals and I/O-mapped symbols are organised
6. A **TcUnit suite**, if you have one

Prefer real, shipped, reviewed code over anything written to be exemplary.

### Before committing house code

- **Customer or site names**, machine serial numbers, project codes
- **IP addresses, AMS NetIDs, credentials** in comments or GVLs
- **Process recipes or setpoints** that are commercially sensitive
- Anything under NDA

Redaction is fine — replacing a customer name with `Customer_A` costs nothing and preserves every structural signal that matters.

### Where to put it

A `house/` folder alongside the three above, with a `NOTES.md` saying what the machine does and anything non-obvious:

```
examples/house/
├── FB_Cylinder.TcPOU
└── NOTES.md      "Pneumatic cylinder, two reed switches; tPositionTimeout
                   comes from the slowest cylinder on the line — measured,
                   not from the spec sheet."
```

No `LICENSE` file needed for your own code. Once it exists, prefer it over everything else here — `SKILL.md` step 1 says to read `examples/` before writing, and house code should win.

## Verifying

Every file here parses with the skill's own tooling:

Run these from the repository root, as everything else in the skill does — with
`../scripts` the globs starting `examples/` cannot resolve from the same directory:

```bash
py -3 scripts/tcpou.py check examples/*/*.TcPOU examples/*/*.TcIO examples/*/*.TcDUT examples/*/*.TcGVL
py -3 scripts/tcpou.py show examples/packml-vffs/FB_Cylinder.TcPOU
```

All ten report `ok`. Two notes are expected and correct: every file uses **LF** line endings rather than CRLF, and the `design-patterns-state/` files were saved by TwinCAT **4022**, not 4024.
