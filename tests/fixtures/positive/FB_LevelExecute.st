// X11: both moves are fed from a level. The first is the field test's B2b prompt
// as given; the second is what an agent delivered next to it. Each starts once,
// on its first rising edge, and never again while the expression stays TRUE.
FUNCTION_BLOCK FB_LevelExecute
VAR_INPUT
    bAutoMode : BOOL;
    bAtHome   : BOOL;
    bPicked   : BOOL;
    fPickPos  : LREAL;
    fPlacePos : LREAL;
    fVelo     : LREAL;
END_VAR
VAR
    fbMovePick  : MC_MoveAbsolute;
    fbMovePlace : MC_MoveAbsolute;
    axisX       : AXIS_REF;
END_VAR
fbMovePick(Axis := axisX, Execute := bAutoMode AND bAtHome, Position := fPickPos, Velocity := fVelo);
fbMovePlace.Execute := bAutoMode AND bPicked AND NOT fbMovePick.Busy;
fbMovePlace(Axis := axisX, Position := fPlacePos, Velocity := fVelo);
END_FUNCTION_BLOCK
