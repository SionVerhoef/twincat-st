// CP8 skips change detection against a latched copy (fTarget <> fSetpoint), but
// a measured position compared exactly with that same target was never copied
// from it and must still fire. A field test found both shapes side by side.
FUNCTION_BLOCK FB_LatchedCompare
VAR_INPUT
  fSetpoint  : LREAL;  // [mm]
  fActPos    : LREAL;  // [mm] from the axis
  bStart     : BOOL;
END_VAR
VAR_OUTPUT
  bSetpointChanged : BOOL;
  bInPosition      : BOOL;
END_VAR
VAR
  fTarget    : LREAL;  // [mm] setpoint latched at start
END_VAR
IF bStart THEN
  fTarget := fSetpoint;
END_IF
bSetpointChanged := (fTarget <> fSetpoint);
bInPosition := (fActPos = fTarget);
END_FUNCTION_BLOCK
