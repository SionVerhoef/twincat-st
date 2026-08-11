# Safety Boundary

**This skill does not author safety logic.** Read this whenever a task touches TwinSAFE, FSoE, emergency stop, guard doors, light curtains, two-hand controls, safe torque off, muting, or any claim about SIL / PL / Category conformance.

## Why the line is here, not somewhere else

A safety function is not "code that is careful". It is a certified artefact:

- It is written in a **certified toolchain** (TwinCAT Safety Editor), on **certified hardware** (EL69xx safety logic terminals, TwinSAFE Logic), with a **certified compiler**.
- It carries a **checksum/CRC and a verified download record** proving the deployed logic matches the reviewed logic.
- It requires **documented risk assessment** (EN ISO 12100), a determined required performance level (EN ISO 13849-1 / IEC 62061), **validation testing**, and **sign-off by a competent person** who accepts liability.

An agent can produce none of these. Code that looks like safety logic but lacks them is worse than no code, because it invites the belief that the hazard is handled. People are injured by that gap.

## What you must not do

- Write, generate, scaffold, or "sketch" TwinSAFE / safety-PLC logic, safety function blocks, or FSoE configuration.
- Implement an E-stop, guard interlock, light-curtain mute, safe-speed monitor, or two-hand control in **standard** PLC code and present it as fulfilling a safety function.
- Modify existing safety project files, safety parameters, safe addresses, or FSoE slave configuration.
- State or imply that any code achieves a SIL level, Performance Level, or Category.
- Advise on bypassing, muting, defeating, or temporarily disabling a safety device — including "just for testing".

## What you may do

- **Read and explain** existing safety configuration, so the user understands what is there.
- Work on the **standard-PLC side of the boundary**: reading the safety system's status signals, reacting to them, and sequencing the process accordingly.
- Implement **process protection** that is explicitly not a safety function — machine-damage interlocks, soft limits, overtemperature holds — clearly labelled as such.
- Explain the architecture and the standards, and point out where a competent person is required.

## The standard-side pattern

The correct division: the safety system decides; the standard PLC observes and reacts.

```pascal
// bSafetyOK is an INPUT from the TwinSAFE logic — the safety system owns this
// decision. Nothing below constitutes a safety function; it exists so the
// process stops tidily and reports why, not to protect anyone.
IF NOT bSafetyOK THEN
    bRunPermissive := FALSE;
    eState         := E_Seq.SafetyHold;
END_IF
```

Note the comment. If you write code in this area, that disclaimer goes in the code, not only in the chat.

## When a task crosses the line

Say so plainly, once, without lecturing, and offer the part you *can* do:

> The guard-door interlock is a safety function — it needs the TwinSAFE toolchain, a risk assessment, and sign-off by a competent person, which I can't provide. What I can do is write the standard-PLC side: reacting to the safety system's status, holding the sequence, and reporting the state to the HMI. Want me to do that part?

Then do that part properly. Do not refuse the whole task, and do not quietly do the safety part anyway.
