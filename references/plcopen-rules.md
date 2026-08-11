# The PLCopen rule catalogue

A review that says "this looks wrong" starts an argument. A review that says **"CP8 (High): floating-point equality at line 47"** ends one, because both people can go and read the same rule.

This is the rule set from the *PLCopen Coding Guidelines v1.0* (2016) — 64 rules in five families, each carrying that document's own **Importance** rating. The rules and their severities are facts about a published standard; the restatements below are original wording. Read the source itself when a rule's exact intent matters — it is a free download from `plcopen.org/downloads`, no registration required.

**How to use it.** Run `scripts/st_review.py` first — it checks the mechanically detectable rules and prints the id. Use this catalogue for the rest: the rules that need judgement, and for citing a severity when you write the review up.

Severity is PLCopen's, not this skill's. Where the reviewer script deviates it says so at the rule.

## Contents

- [Naming — N1…N10](#naming--n1n10)
- [Comments — C1…C6](#comments--c1c6)
- [Coding practice — CP1…CP28](#coding-practice--cp1cp28)
- [Language and layout — L1…L17](#language-and-layout--l1l17)
- [Vendor extensions — E1…E3](#vendor-extensions--e1e3)
- [Reading the severities](#reading-the-severities)

Legend for the **Tool** column: ● checked by `scripts/st_review.py` · ◐ partially checked · ○ needs a human.

## Naming — N1…N10

| Id | Sev | Rule | Tool |
|---|---|---|---|
| N1 | High | Don't bind logic to physical addresses (`%IX0.1`). Declare a symbolic variable and map it in the I/O configuration, so re-wiring is a mapping change rather than a code change. | ○ |
| N2 | Low | If the project uses type prefixes, define them once and apply them everywhere. PLCopen is deliberately neutral on *whether* to prefix — see `naming-conventions.md` for what the TwinCAT world actually does. | ○ |
| N3 | High | Define the names that are forbidden — keywords, vendor-reserved words, and anything that shadows a standard function. | ○ |
| N4 | High | Fix a capitalisation scheme and hold to it. ST is case-insensitive, so `Motor` and `motor` are one name; inconsistent case makes search and review unreliable. | ○ |
| N5 | High | A local name must not shadow a global one. The reader cannot tell which is in play, and the compiler will not warn. | ○ |
| N6 | Medium | Keep names in a sensible length band — PLCopen suggests a minimum of 8 (3 for locals), a maximum of 25, averaging about 15. Avoid names differing only in case or by one letter. | ○ |
| N7 | Medium | Define a namespace convention if the project uses libraries that could collide. | ○ |
| N8 | Medium | Define the permitted character set — ASCII identifiers travel; accented characters and symbols do not. | ○ |
| N9 | Medium | Two different kinds of element must not share a name (an FB and a variable both called `Motor`). | ○ |
| N10 | Low | Give user-defined types a prefix convention (`ST_`, `E_`, `I_`, `T_`). | ○ |

## Comments — C1…C6

| Id | Sev | Rule | Tool |
|---|---|---|---|
| C1 | High | Comments state the **intention**, not the mechanics. `nCount := nCount + 1; // increment count` is noise; a comment explaining *why the filter is 50 ms* is not. | ○ |
| C2 | High | Every element gets a comment — POUs, and each declaration. For a physical value the comment carries the **unit**, which is the single highest-value comment in PLC code. | ○ |
| C3 | Low | Don't nest comments; behaviour varies by compiler. | ○ |
| C4 | Low | Don't leave commented-out code. It rots, and version control already remembers it. | ○ |
| C5 | Low | Prefer single-line comments — a stray unclosed `(*` can swallow a whole POU. | ○ |
| C6 | Low | Pick one language for comments and identifiers and hold to it across the project. | ○ |

## Coding practice — CP1…CP28

The substantive family. Everything here is High unless marked.

| Id | Sev | Rule | Tool |
|---|---|---|---|
| CP1 | High | Reach a structure member by name, never by memory offset. | ○ |
| CP2 | High | All code is reachable and used. Dead POUs are a maintenance trap and may silently become live. | ○ |
| CP3 | High | Every variable is initialised before it is read. Initial values apply on download and cold reset — **not** on a warm start — so code relying on "it starts at zero" is wrong. | ○ |
| CP4 | High | Directly-addressed memory must not overlap. Two names over one address is an aliasing bug you cannot see. | ○ |
| CP5 | High | Design the application before writing it: modularise, encapsulate, group related data into structures and arrays, keep FB internals private. | ○ |
| CP6 | High | Avoid `VAR_EXTERNAL` inside functions and function blocks — a hidden global dependency destroys reusability and testability. | ◐ |
| CP7 | High | **Test the error information a call returns.** If a block has `Error`/`ErrorID`, read them and change behaviour. An unread error means either the developer missed a case or the error genuinely cannot matter — and the reader cannot tell which. | ○ |
| CP8 | High | Never compare floating point with `=` or `<>`. Compare against a tolerance. | ● |
| CP28 | High | Same for `TIME` and physical measures — a scan steps *over* an exact value rather than landing on it. Use `>=`. | ● |
| CP9 | High | Bound POU complexity and split what exceeds it. PLCopen declines to mandate one metric; the point is that you *have* a limit. | ○ |
| CP10 | High | Don't write the same variable from more than one task. | ○ |
| CP11 | High | Synchronise data shared across tasks. Multi-word data crossing a task boundary can be read mid-update; transfer it as one structure under a handshake. | ○ |
| CP12 | High | Write each physical output exactly once per cycle, ideally in one place at the end. Output logic scattered through the program is both non-deterministic and unmaintainable. | ○ |
| CP13 | High | No recursion, direct or indirect. Stack depth is not bounded and vendor support varies. | ● |
| CP14 | High | Single point of exit — avoid `RETURN` before the end of a POU. *The reviewer holds this back behind `--pedantic`: the early-return guard clause is widespread and defensible, and enforcing it by default buries real defects.* | ● |
| CP15 | High | Read a variable written by another task only once per cycle; copy it locally and use the copy, or different parts of the scan see different values. | ○ |
| CP16 | High | Tasks call **PROGRAM** POUs only, never a function block directly. Binding a task to an FB instance makes execution control ambiguous and is not portable. | ○ |
| CP17 | High | Parameter direction must match use: inputs are read and not written, outputs are written, in-outs are both. | ◐ |
| CP18 | High | Limit globals. They are justified for exchanging data between programs or tasks, with the system, and with physical I/O — otherwise prefer locals. | ○ |
| CP19 | Medium | Avoid jump and return constructs; never jump backwards. | ◐ |
| CP20 | Medium | Call a function-block instance once per cycle. **The call may be conditional** — the rule is about one *invocation*, not about calling unconditionally. *The reviewer reports this at low severity because text cannot prove two call sites are reachable in the same scan.* See the note below. | ● |
| CP21 | Medium | Use `VAR_TEMP` for genuinely temporary values such as loop counters, so they cannot carry state between calls by accident. | ○ |
| CP22 | Medium | Choose the data type for the range and the operations: smallest type that fits, unsigned for unsigned data, enumerations and subranges where they apply, and don't use one type everywhere to dodge conversions. | ○ |
| CP23 | Medium | Cap the parameter count — PLCopen suggests around **10** inputs/outputs/in-outs. Beyond that, group them into a `STRUCT` or move configuration into `FB_init`. | ● |
| CP24 | Medium | Don't declare variables you never use. | ● |
| CP25 | Medium | *(numbering note: this id sits with the "unused/declaration" group; treat it with CP24.)* | ○ |
| CP26 | Low | Make type conversions explicit (`DINT_TO_REAL(x)`), never implicit. | ○ |
| CP27 | Low | Avoid deprecated language features. | ○ |

### CP20 is narrower than "always call unconditionally"

Worth stating precisely, because the two ideas get merged and the merged version is wrong.

- **CP20 says:** invoke a given instance at most once per cycle; a conditional call is allowed.
- **The cyclic-execution rule says:** a *stateful, pending-operation* block — PLCopen motion, comms, file access — must keep being called while an operation is in flight, or it never finishes, never times out and never reports an error.

They agree. The second is not "call every FB unconditionally forever"; it is "while `Busy` is true, keep calling". A simple stateless helper FB called inside one branch of a `CASE` breaks neither rule. See `cyclic-execution-rules.md` Rule 2.

## Language and layout — L1…L17

Only the ST-relevant rules are listed; L2, L3, L5–L9 govern FBD, Ladder and SFC.

| Id | Sev | Rule | Tool |
|---|---|---|---|
| L1 | Low | Define an indentation convention. | ○ |
| L4 | Low | Define general ST formatting rules. | ○ |
| L10 | Medium | Avoid `CONTINUE` and `EXIT` — they make a loop's exit conditions non-local. | ○ |
| L11 | Medium | Maximum line length **80** characters; break long calls one parameter per line. *Reviewer: `--pedantic`.* | ● |
| L12 | Medium | *(layout family — see the source.)* | ○ |
| L13 | Medium | Don't use the `FOR` loop variable after the loop; its final value is not guaranteed. | ○ |
| L22 | Medium | Don't modify the loop variable inside a `FOR` loop. | ○ |
| L14 | Medium | Pass parameters explicitly and readably — name them at the call site rather than relying on position. | ○ |
| L15 | Medium | Parenthesise to make precedence explicit rather than relying on the reader knowing the table. | ○ |
| L16 | Low | Define whether tabs or spaces are used. | ○ |
| L17 | Low | Give every `IF` an `ELSE`. Defensive; PLCopen treats it as a requirement for safety-critical software and optional elsewhere. The same instinct applied to `CASE` is rule `X3` in the reviewer, where it matters more — an unhandled state is a stuck machine. | ◐ |

## Vendor extensions — E1…E3

These govern the pointer and allocation features vendors added beyond the standard. All High.

| Id | Sev | Rule | Tool |
|---|---|---|---|
| E1 | High | No dynamic allocation. `__NEW`/`__DELETE` in cyclic code makes execution time unbounded and invites leaks and fragmentation on a controller that must run for months. | ● |
| E2 | High | No pointer arithmetic to reach adjacent data. Use an array and index it. | ◐ |
| E3 | High | Only `=` and `<>` are defined on pointers and references. `<`, `>`, `<=`, `>=` depend on undocumented memory layout. | ● |

## Reading the severities

PLCopen's rating measures effect on software quality, not how often the rule is broken. Two consequences worth keeping in mind:

- **A High rule that is easy to satisfy is still worth citing** — CP8 costs one tolerance constant.
- **A Medium rule can matter more than a High one in context.** CP23 (parameter count) is Medium, but an FB with 20 pins on a machine someone else maintains is a bigger practical problem than a missed `ELSE`.

And the whole catalogue is downstream of the thing this skill cares about most: none of these rules catch a blocking `WHILE` loop in a cyclic task. That is why the reviewer carries its own `X` family. Cite PLCopen when it applies; don't pretend it covers the execution model, because it does not.
