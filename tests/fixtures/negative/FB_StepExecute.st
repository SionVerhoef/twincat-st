// X11 must stay quiet on every Execute here. A step comparison is edge-correct
// because the step changes; a trigger's .Q is an edge by construction; a lone
// command bit is set and cleared by whoever owns it, which the text cannot judge.
FUNCTION_BLOCK FB_StepExecute
VAR_INPUT
    bStart  : BOOL;
    bEnable : BOOL;
    bJog    : BOOL;
    fPos    : LREAL;
    fVelo   : LREAL;
END_VAR
VAR_OUTPUT
    bFault  : BOOL;
END_VAR
VAR
    eStep    : E_Step;
    fbMove   : MC_MoveAbsolute;
    fbJog    : MC_MoveVelocity;
    fbHome   : MC_Home;
    fbTrig   : R_TRIG;
    bHomeCmd : BOOL;
    axisX    : AXIS_REF;
END_VAR
fbTrig(CLK := bJog);
fbMove(Axis := axisX, Execute := (eStep = E_Step.Move) AND bEnable, Position := fPos,
       Velocity := fVelo);
fbJog(Axis := axisX, Execute := fbTrig.Q AND bEnable, Velocity := fVelo);
fbHome(Axis := axisX, Execute := bHomeCmd);
fbHome.Execute := bStart;
bFault := fbMove.Error OR fbJog.Error OR fbHome.Error;
END_FUNCTION_BLOCK
