# Testing with TcUnit

PLC code has a reputation for being untestable. Most of that is a design problem rather than a platform problem: an FB that talks straight to `%IX0.1` cannot be tested anywhere but on the machine, and an FB that takes an `I_Cylinder` can be tested at a desk.

**TcUnit** is the de-facto unit-test framework for TwinCAT 3 (0BSD licence, so it can be vendored freely). Tests are ordinary PLC code that runs on the target — or on a local runtime — and reports results to the error list.

## The shape

A test suite is a function block extending `FB_TestSuite`. Its **body** calls each test method; each method runs the code under test and asserts.

Where the fixtures are declared decides what you can test. A method's `VAR` is `VAR_TEMP` — re-initialised on every call — so it suits a **single-cycle** test of a pure function, and nothing else. Anything **stateful**, where the FB needs several scans to reach a verdict, must declare its fixtures on the **suite**, or the instance resets before it can get anywhere. The multi-cycle section below is the shape to copy for those.

```pascal
FUNCTION_BLOCK FB_Scaling_Tests EXTENDS FB_TestSuite

// body — one line per test
WhenRawIsZeroExpectMinimum();
WhenRawIsFullScaleExpectMaximum();
WhenRawBelowRangeExpectError();
```

```pascal
METHOD PRIVATE WhenRawIsZeroExpectMinimum
VAR
    fbScale : FB_AnalogScale;
    fResult : LREAL;
END_VAR

TEST('WhenRawIsZeroExpectMinimum');

// @TEST-RUN
fbScale(nRaw := 0, fMin := 4.0, fMax := 20.0, fValue => fResult);

// @TEST-ASSERT
AssertEquals_LREAL(
    Expected := 4.0,
    Actual   := fResult,
    Delta    := 1E-6,                       // never compare LREAL exactly
    Message  := 'Zero raw count should map to the range minimum');

TEST_FINISHED();
```

Three conventions worth keeping, all visible in the reference projects:

- **`When<Condition>Expect<Result>` naming.** The test list then reads as a specification, and a failure message names the behaviour rather than a line number.
- **`TEST(...)` opens and `TEST_FINISHED()` closes.** Forgetting the close leaves the suite waiting forever, which presents as a hang rather than a failure.
- **`Delta` on every float assertion.** `AssertEquals_LREAL` without a tolerance is PLCopen CP8 wearing a test-framework hat.

Suites are registered by instantiating them, typically in a `PRG_TEST` program that the test task calls. The instance existing is the registration — there is nothing to "call", which is why `scripts/st_review.py` deliberately does not report an unreferenced FB instance as an unused variable.

## What to test, given the cycle

The awkward part of testing PLC code is that most interesting behaviour takes more than one scan. Three approaches, in order of preference:

1. **Test the pure parts directly.** Scaling, unit conversion, limit logic, CRC, recipe validation — no state, no time, one call, one assertion. Most of the arithmetic that goes wrong on a machine is testable this way, and these tests are worth writing first.

2. **Drive a state machine across real cycles.** This is the part people get wrong, and it is worth being precise about.

   A loop does **not** work:

   ```pascal
   // WRONG - all ten calls happen in the SAME scan, so no time passes and
   // no TON inside the sequence ever elapses. The test asserts on a machine
   // that has effectively not run.
   FOR nScan := 1 TO 10 DO
       fbSeq(bExecute := TRUE);
   END_FOR
   AssertTrue(fbSeq.bDone, '...');
   ```

   Neither does declaring the fixture inside the test method: for methods, `VAR` behaves as `VAR_TEMP` (PLCopen CP21), so the instance is re-initialised on every call and can never accumulate state.

   The pattern that works puts the fixture on the **suite** and calls the FB once per cycle, finishing the test only when a verdict is available:

   ```pascal
   FUNCTION_BLOCK FB_Filling_Tests EXTENDS FB_TestSuite
   VAR
       fbSeq      : FB_Filling;     // suite-level: survives between cycles
       fbWatchdog : TON;
   END_VAR
   ```

   ```pascal
   TEST('WhenStartedExpectDone');

   fbSeq(bExecute := TRUE);                       // exactly one call per scan
   fbWatchdog(IN := TRUE, PT := T#10S);

   IF fbSeq.bDone THEN
       AssertFalse(fbSeq.bError, 'Reached Done but reported an error');
       TEST_FINISHED();
   ELSIF fbWatchdog.Q THEN
       AssertTrue(FALSE, 'Did not reach Done within the watchdog');
       TEST_FINISHED();
   END_IF
   ```

   TcUnit calls the suite body every cycle until each test calls `TEST_FINISHED()`, which is what makes this work. **Always include the watchdog branch:** a test whose condition never arrives simply never finishes, and the suite hangs with no failure reported — which looks exactly like a test that has not run yet.

3. **Inject the device.** An FB that depends on `I_Cylinder` rather than a concrete cylinder can be given a stub that reports confirmation on demand — including failure and timeout paths, which are otherwise almost impossible to exercise. This is dependency inversion (see `oop.md`) paying for itself.

Timeouts deserve particular attention: the timeout branch of a sequence is the code most likely to be wrong and least likely to be exercised on a good day. A stub that simply never confirms tests it in milliseconds.

## What TcUnit will not do for you

- **It runs on a runtime.** There is no PLC runtime in this environment, so tests written here are unverified until someone runs them. Say so.
- **It does not check timing.** A test proves logical behaviour across N scans, not that the code fits a 1 ms task.
- **It does not replace review.** Nothing in a passing test suite catches "this FB instance is called from two places" or "this is secretly a safety function".

## CI

`TcUnit-Runner` drives a build and test run headlessly on a Windows machine with TwinCAT installed, which is the only way to get real compiler errors — the reason rung 2 in `SKILL.md` exists. A Linux runner cannot do this: `matiec` and `rusty` reject the OOP constructs this dialect is built on, so a clean parse there would prove nothing while looking like a pass.

If a project has no CI, the honest position is that `scripts/st_review.py` plus a careful read is rung 3, and to name it as such.

## A starting point

`templates/FB_ExampleTestSuite.TcPOU` is a working suite skeleton using the across-cycles pattern above: fixtures on the suite, one call per scan, a watchdog on every test. It covers both the completion path and the timeout path, since the timeout branch is the one most likely to be wrong.

Before trusting a green result, confirm the harness actually ran. A suite that never executes reports no failures, which is indistinguishable from success.
