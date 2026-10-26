// X13 stays silent. A remembered operating mode is chosen by the operator, not
// stepped by its own CASE, and a remanent part counter selects nothing. The step
// counter of the sequence is a plain VAR, the shape Rule 9 asks for.
FUNCTION_BLOCK FB_RemanentMode
VAR_INPUT
    nModeRequest : INT;
    bPart        : BOOL;
    bStart       : BOOL;
END_VAR
VAR_OUTPUT
    fSpeed : LREAL;
    bError : BOOL;
END_VAR
VAR PERSISTENT
    nMode      : INT;
    nPartCount : UDINT;
END_VAR
VAR
    nStep  : INT;
    fbPart : R_TRIG;
END_VAR
IF nModeRequest > 0 THEN
    nMode := nModeRequest;
END_IF
CASE nMode OF
    1: fSpeed := 0.5;
    2: fSpeed := 1.0;
ELSE
    fSpeed := 0.0;
END_CASE
fbPart(CLK := bPart);
IF fbPart.Q THEN
    nPartCount := nPartCount + 1;
END_IF
CASE nStep OF
    0:  IF bStart THEN nStep := 10; END_IF
    10: IF NOT bStart THEN nStep := 0; END_IF
    99: bError := TRUE;
        IF NOT bStart THEN bError := FALSE; nStep := 0; END_IF
ELSE
    nStep := 99;
END_CASE
END_FUNCTION_BLOCK
