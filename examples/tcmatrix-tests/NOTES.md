# TcUnit test structure — TcMatrix

**Source:** [BurksEngineering/TcMatrix](https://github.com/BurksEngineering/TcMatrix) · MIT · Copyright (c) 2021 BurksEngineering · see `LICENSE`
**What it is:** a matrix maths library for TwinCAT with a full companion test project — the clearest available example of how a unit-tested TwinCAT library is laid out.

Two files: one test suite, and the runner that executes every suite.

## `PRG_TEST.TcPOU` — the runner

The whole thing is a declaration block instantiating fifteen test-suite function blocks, and a one-line body:

```pascal
TcUnit.RUN();
```

That is the entire TcUnit wiring. **Declaring a suite instance is what registers it** — `TcUnit.RUN()` discovers and drives them; you never call a suite yourself. Forgetting the instance is how a suite silently never runs.

Put this program on its own task, and keep the whole `TESTs/` folder out of the release build.

## `FB_MatrixInvert_Test.TcPOU` — one suite

`FUNCTION_BLOCK FB_MatrixInvert_Test EXTENDS FB_TestSuite`. The body calls each test method unconditionally:

```pascal
WhenIdentityExpectIdentity();
WhenSingularExpectError();
WhenSolvableExpectSolution();
```

Each method is `METHOD PRIVATE`, and follows a fixed shape:

```pascal
TEST('WhenSingularExpectError');

// @TEST-RUN
M1.InitTrapezoidal(3,3,1,1,1);
Result := M2.AsInverse(M1, 1E-9);

// @TEST-ASSERT
AssertFalse(Result, 'Main function call was surprisingly successful');

TEST_FINISHED();
```

Three things worth copying:

1. **`When<condition>Expect<outcome>` naming.** The method name states the whole test. A failure report reads as a sentence, which matters because TcUnit results arrive as a flat list in the error window with no context around them.
2. **`// @TEST-RUN` / `// @TEST-ASSERT` sections.** A convention, not a TcUnit feature — but it makes arrange/act/assert visible at a glance and stops setup and assertion blurring together.
3. **Assertion messages that describe the failure, not the assertion.** *"Main function call was surprisingly successful"* tells you what went wrong. `'AssertFalse failed'` would not.

Note the singular-matrix case: the suite tests the **error path** as a first-class case, not only the happy path. That is the habit worth importing — a PLC FB's error path is the part that runs at 3am.

## Why a maths library is a good testing example

It is deliberately the easy case: pure functions, no I/O, no cycle-dependent state, so tests need no simulation. That is exactly why it is worth studying — it shows the test *structure* without the complication of faking a machine.

The harder case is a device or sequence FB, where a test must drive the FB across many cycles before asserting. `templates/FB_ExampleTestSuite.TcPOU` sketches that shape: fixtures declared on the **suite** so they survive between cycles, one call per scan, and the assertion made when a verdict arrives. A `FOR` loop of calls cannot stand in for it — the loop body runs entirely within one scan, so no time passes and no `TON` inside the FB can elapse. Getting there is why `naming-conventions.md` argues for FBs whose only contact with the outside world is their interface — an FB that reaches into a GVL cannot be tested this way.
