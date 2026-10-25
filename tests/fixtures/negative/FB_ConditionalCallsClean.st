// X12, CP7 and CP12 must stay quiet on every shape here. A timer reset with
// IN := FALSE on the way into its state, blocks called unconditionally, an Error
// bound with '=>', read as a member, or handed on whole, and an output written in
// both branches of one IF are all correct.
FUNCTION_BLOCK FB_ConditionalCallsClean
VAR_INPUT
    bStart   : BOOL;
    bSensor  : BOOL;
    fPos     : LREAL;    // mm
END_VAR
VAR_OUTPUT
    bFault   : BOOL;
END_VAR
VAR
    eStep    : E_Step;
    tonWait  : TON;
    tonStep  : TON;
    fbEdge   : R_TRIG;
    fbMove   : MC_MoveAbsolute;
    fbPower  : MC_Power;
    fbHome   : MC_Home;
    axisX    : AXIS_REF;
    bMoveErr : BOOL;
    qbValve AT %Q* : BOOL;
END_VAR
fbEdge(CLK := bSensor);
tonStep(IN := eStep = E_Step.Settle, PT := T#500MS);
CASE eStep OF
    E_Step.Idle:
        IF bStart THEN
            tonWait(IN := FALSE);   // lint:allow CP20 the reset on the way into Wait
            eStep := E_Step.Wait;
        END_IF
    E_Step.Wait:
        tonWait(IN := TRUE, PT := T#2S);
        IF tonWait.Q OR fbEdge.Q THEN
            eStep := E_Step.Settle;
        END_IF
    E_Step.Settle:
        IF tonStep.Q THEN
            eStep := E_Step.Idle;
        END_IF
    E_Step.Error:
        eStep := E_Step.Idle;
ELSE
    eStep := E_Step.Error;
END_CASE
fbPower(Axis := axisX, Enable := TRUE);
fbMove(Axis := axisX, Execute := eStep = E_Step.Settle, Position := fPos,
       Velocity := 50.0, Error => bMoveErr);
fbHome(Axis := axisX, Execute := bStart);
IF bMoveErr OR fbPower.Error THEN
    qbValve := FALSE;
ELSE
    qbValve := eStep = E_Step.Wait;
END_IF
bFault := CheckHome(fbHome);
END_FUNCTION_BLOCK

METHOD CheckHome : BOOL
VAR_IN_OUT
    fbBlock : MC_Home;
END_VAR
CheckHome := fbBlock.Error;
END_METHOD
