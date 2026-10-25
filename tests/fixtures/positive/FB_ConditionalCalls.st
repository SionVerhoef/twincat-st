// X12: a timer, a trigger and a motion block each called only inside a branch.
// CP7: the motion block's Error is never read, nor is the house FB's bError.
// CP12: the valve output is written from the body and from a method.
FUNCTION_BLOCK FB_Device
VAR_INPUT
    bExecute : BOOL;
END_VAR
VAR_OUTPUT
    bDone    : BOOL;
    bError   : BOOL;
END_VAR
bDone := bExecute;
bError := FALSE;
END_FUNCTION_BLOCK

FUNCTION_BLOCK FB_ConditionalCalls
VAR_INPUT
    bStart   : BOOL;
    bSensor  : BOOL;
    fPos     : LREAL;    // mm
END_VAR
VAR_OUTPUT
    bBusy    : BOOL;
END_VAR
VAR
    eStep    : E_Step;
    tonWait  : TON;
    fbEdge   : R_TRIG;
    fbMove   : MC_MoveAbsolute;
    fbDevice : FB_Device;
    axisX    : AXIS_REF;
    qbValve AT %Q* : BOOL;
END_VAR
CASE eStep OF
    E_Step.Idle:
        IF bStart THEN
            eStep := E_Step.Wait;
        END_IF
    E_Step.Wait:
        tonWait(IN := TRUE, PT := T#2S);
        fbEdge(CLK := bSensor);
        IF tonWait.Q OR fbEdge.Q THEN
            eStep := E_Step.Move;
        END_IF
    E_Step.Move:
        fbMove(Axis := axisX, Execute := TRUE, Position := fPos, Velocity := 50.0);
        IF fbMove.Done THEN
            eStep := E_Step.Idle;
        END_IF
    E_Step.Error:
        eStep := E_Step.Idle;
ELSE
    eStep := E_Step.Error;
END_CASE
fbDevice(bExecute := bStart);
qbValve := eStep = E_Step.Move;
bBusy := fbDevice.bDone;
END_FUNCTION_BLOCK

METHOD CloseValve
qbValve := FALSE;
END_METHOD
