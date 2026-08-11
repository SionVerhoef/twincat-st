# CODESYS — vendor specifics

> **UNTESTED.** There is no CODESYS installation available to verify any of this against, and none
> of the reference code this skill was built from is CODESYS-specific. TwinCAT guidance here can be
> checked against real sample projects; the contents of this file cannot.
>
> **Say so when you use it.** "This is the CODESYS path, which this skill has not verified" is a
> required disclaimer, not a hedge. Getting this wrong in front of a controls engineer is the
> failure mode the whole scope decision was built to avoid.

## What transfers unchanged

TwinCAT 3's PLC layer is derived from CODESYS V3 and shares its OOP extensions, so roughly 75% of this skill applies as written. Everything in the core is safe:

- ST syntax — types, operators, control flow, `CASE`, loops
- The POU model — `PROGRAM` / `FUNCTION_BLOCK` / `FUNCTION`, `VAR` sections, `VAR_IN_OUT` semantics
- All OOP constructs — `METHOD`, `PROPERTY`, `INTERFACE`, `EXTENDS`, `IMPLEMENTS`, `ABSTRACT`, `THIS^`, `SUPER^`
- Naming conventions (PLCopen-based)
- State-machine patterns, including PackML
- Error-handling and diagnostics patterns
- **Everything in `cyclic-execution-rules.md`** — the scan-cycle model is identical

That last point is the important one: the highest-value file in this skill is fully portable.

## The seam

| Area | TwinCAT 3 | CODESYS |
|---|---|---|
| Standard libraries | `Tc2_Standard`, `Tc2_System`, `Tc2_Utilities`, `Tc3_*` | CODESYS `Standard`, `Util`, `SysLibs` |
| Source format | `.TcPOU` / `.TcDUT` / `.TcGVL` / `.TcIO` XML | `.project` container; PLCopenXML for exchange |
| Project files | `.plcproj` + `.tsproj` | `.project` |
| Motion | NC/PTP via `Tc2_MC2` (PLCopen `MC_*`) | SoftMotion (also PLCopen `MC_*`) |
| Fieldbus | EtherCAT-native, tight I/O integration | vendor-dependent |
| IDE | XAE, hosted in Visual Studio | CODESYS IDE (Eclipse-derived) |
| Unit testing | TcUnit | CODESYS Test Manager, or TcUnit-alikes |
| Remote access | ADS | OPC UA / vendor gateways |
| Packaging | Twinpack, TcPkg | CODESYS Store |

## What does not carry over

- **`scripts/tcpou.py` does not apply.** CODESYS stores projects in a `.project` container, not loose XML files. Use PLCopenXML export/import for text-level work instead.
- **`references/twincat/project-files.md` does not apply** for the same reason. The git-hygiene advice largely does not either — a `.project` container is far less diffable than `.TcPOU` files.
- **`references/twincat/ads-and-diagnostics.md` does not apply.** ADS is Beckhoff's protocol; CODESYS systems typically expose OPC UA.
- **Motion is the friendly case.** Both implement PLCopen `MC_*` blocks, so the block contracts in `st-language.md` hold. The seam is axis configuration and setup, not the function-block interfaces.

## Other CODESYS V3 family members

Schneider EcoStruxure Machine Expert, Festo, WAGO, Lenze, Eaton and Bosch Rexroth all build on CODESYS V3. The core applies; each adds its own library set and tooling on top. None has been verified here either — the same disclaimer applies, more strongly.

## Honest limits

The 75/25 core-versus-seam split is **reasoned from the table above, not measured.** Treat it as a rough expectation rather than a figure to quote.
