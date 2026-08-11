# Attributions

What this skill was built from, and what each source gave it.

## Standards

| Source | What it contributed |
|---|---|
| PLCopen *Coding Guidelines v1.0* (2016) | The rule catalogue in `references/plcopen-rules.md` — 64 rule ids, their names and their severity ratings — and most of the review rubric. |
| PLCopen *Creating PLCopen compliant Function Block libraries v1.0* (2017) | The behaviour model in `references/behaviour-model.md`: edge-triggered vs level-controlled interfaces, the state names, and the abort and timeout variants. |
| PLCopen *Guidelines for usage of OOP v1.0* (2021) | SOLID applied to function blocks, and the module/command framing in `references/oop.md`. |
| PLCopen *Mapping of OMAC PackML to IEC 61131-3* | The PackML state model in `references/patterns.md`. PackML itself is an OMAC specification. |
| IEC 61131-3 summaries (via PLCopen) | Data types, the POU model and language details in `references/st-language.md`. |
| Beckhoff Information System | The TwinCAT library and tooling details in `references/twincat.md`. |

These are copyrighted documents. The rules were read and restated in original words; rule identifiers and severities are quoted as such.

## Code

| Source | What it contributed |
|---|---|
| Beckhoff OOP samples (InfoSys) | The five-layer machine structure and the cylinder inheritance chain discussed in `references/patterns.md` and `references/oop.md`. |
| TcUnit and its sample projects | The test-suite shape in `references/testing-tcunit.md` and `templates/FB_ExampleTestSuite.TcPOU`. |
| Stefan Henneken's IEC 61131 series, Beckhoff-USA-Community, TcMatrix, fisothemes, the PackML example | Read as a corpus and measured. The naming statistics and idiom counts throughout the references come from counting these ~1,800 `.TcPOU` files. |
| `pyads` | The platform behaviour in `references/twincat/ads-and-diagnostics.md` was read from its source. |

## Files redistributed in `examples/`

Everything outside `examples/` was written for this skill. `examples/` ships ten unmodified source files from three permissively-licensed projects, so that the skill can show real code rather than describe it. Each folder carries a verbatim copy of its upstream `LICENSE` — MIT and BSD-2 both require the notice to travel with the files, and a link back to GitHub does not satisfy either.

| Folder | Files | Upstream | Licence | Copyright |
|---|---|---|---|---|
| `examples/packml-vffs/` | `MAIN.TcPOU`, `FB_EquipmentModuleTemplate.TcPOU`, `FB_Cylinder.TcPOU`, `I_Cylinder.TcIO`, `ST_Cylinder_Config.TcDUT` | [Beckhoff-USA-Community/PackML_PLC_Example](https://github.com/Beckhoff-USA-Community/PackML_PLC_Example) | MIT | © 2023 Beckhoff Automation LLC |
| `examples/tcmatrix-tests/` | `FB_MatrixInvert_Test.TcPOU`, `PRG_TEST.TcPOU` | [BurksEngineering/TcMatrix](https://github.com/BurksEngineering/TcMatrix) | MIT | © 2021 BurksEngineering |
| `examples/design-patterns-state/` | `I_State.TcIO`, `FB_ATM_Machine.TcPOU`, `Param.TcGVL` | [0w8States/PLC-Design-Patterns](https://github.com/0w8States/PLC-Design-Patterns) | BSD 2-Clause | © 2021 John Helfrich |

The `NOTES.md` in each folder is original commentary written for this skill, not part of the upstream project.

## Adding material later

If you copy in a file from somewhere else, in the same commit:

1. **Check the licence permits it** — MIT, 0BSD, BSD-2 and Apache-2 do. Read the upstream `LICENSE` file rather than a badge; Beckhoff repositories marked `NOASSERTION` are Zero-Clause BSD, the one case needing no notice.
2. **Put a verbatim `LICENSE` copy in the folder** with the files.
3. **Add a row to the table above**, and say whether you modified anything.

Anything copyleft, and any vendor documentation or standard, gets read and restated in your own words instead — vendoring a GPL file would relicense this whole skill.

Code you wrote yourself is not third-party and needs none of this.

## Trademarks

"TwinCAT" and "Beckhoff" are trademarks of Beckhoff Automation GmbH & Co. KG. "EtherCAT" is a registered trademark and patented technology, licensed by Beckhoff Automation GmbH, Germany. "CODESYS" is a trademark of CODESYS GmbH. "PLCopen" is a trademark of PLCopen. "PackML" and "OMAC" are marks of their respective organisations.

All are used to describe what this skill works with. None of these organisations is affiliated with it or endorses it.
