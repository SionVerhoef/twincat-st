// X7 and X3 must stay quiet on the second CASE. It only picks a value per step,
// a step without a label keeps the last one on purpose, and the state variable it
// reads has an error state and an ELSE in the main CASE above it.
FUNCTION_BLOCK FB_SecondaryCase
VAR_INPUT
    bStart : BOOL;
    bReset : BOOL;
END_VAR
VAR_OUTPUT
    bError : BOOL;
END_VAR
VAR
    eStep   : E_Step;
    fTarget : LREAL;   // [mm]
END_VAR
CASE eStep OF
    E_Step.Idle:
        IF bStart THEN
            eStep := E_Step.Move;
        END_IF
    E_Step.Move:
        eStep := E_Step.Idle;
    E_Step.DeviceError:
        bError := TRUE;
        IF bReset THEN
            bError := FALSE;
            eStep := E_Step.Idle;
        END_IF
ELSE
    eStep := E_Step.DeviceError;
END_CASE

CASE eStep OF
    E_Step.Idle:
        fTarget := 0.0;
    E_Step.Move:
        fTarget := 120.0;
END_CASE
END_FUNCTION_BLOCK
