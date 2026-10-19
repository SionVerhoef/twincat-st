FUNCTION_BLOCK FB_ChangeDetect
VAR_INPUT
  fSetpoint  : LREAL;  // [mm]
  bStart    : BOOL;
END_VAR
VAR_OUTPUT
  bSetpointChanged : BOOL;
END_VAR
VAR
  fTarget    : LREAL;  // [mm] setpoint latched at start
END_VAR
IF bStart THEN
  fTarget := fSetpoint;
END_IF
bSetpointChanged := (fTarget <> fSetpoint);
END_FUNCTION_BLOCK
