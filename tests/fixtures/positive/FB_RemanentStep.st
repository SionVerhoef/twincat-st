// X13: a state machine's step declared remanent, in both forms Haiku wrote in the
// homed-survives-restart eval: a VAR RETAIN block, and the qualifier after the type.
// X14: that second form, which is not where IEC 61131-3 puts the qualifier.
FUNCTION_BLOCK FB_RemanentStep
VAR_INPUT
    bStart  : BOOL;
    bAtHome : BOOL;
END_VAR
VAR_OUTPUT
    bHomed : BOOL;
    bError : BOOL;
END_VAR
VAR RETAIN
    nStep : INT;
END_VAR
VAR
    nPhase : INT PERSISTENT;
END_VAR
CASE nStep OF
    0:  IF bStart THEN nStep := 10; END_IF
    10: IF bAtHome THEN bHomed := TRUE; nStep := 20; END_IF
    20: IF NOT bStart THEN bHomed := FALSE; nStep := 0; END_IF
    99: bError := TRUE;
        IF NOT bStart THEN bError := FALSE; nStep := 0; END_IF
ELSE
    nStep := 99;
END_CASE
CASE nPhase OF
    0: IF bHomed THEN nPhase := 1; END_IF
    1: IF NOT bHomed THEN nPhase := 0; END_IF
ELSE
    nPhase := 0;
END_CASE
END_FUNCTION_BLOCK
