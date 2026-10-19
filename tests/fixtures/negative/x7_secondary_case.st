TYPE E_Step :
(
  Idle    := 0,
  MoveA    := 10,
  MoveB    := 20,
  DeviceError  := 900
);
END_TYPE

FUNCTION_BLOCK FB_TwoCases
VAR_INPUT
  bGo      : BOOL;
  bFault    : BOOL;
  bReset    : BOOL;
END_VAR
VAR
  eStep    : E_Step;
  fTarget    : LREAL;  // [mm]
END_VAR
IF bFault THEN
  eStep := E_Step.DeviceError;
END_IF
CASE eStep OF
  E_Step.Idle:    IF bGo THEN eStep := E_Step.MoveA; END_IF
  E_Step.MoveA:    eStep := E_Step.MoveB;
  E_Step.MoveB:    eStep := E_Step.Idle;
  E_Step.DeviceError:  IF bReset THEN eStep := E_Step.Idle; END_IF
ELSE
  eStep := E_Step.DeviceError;
END_CASE
// Pick a target per step; other steps keep the last one
CASE eStep OF
  E_Step.MoveA:  fTarget := 100.0;
  E_Step.MoveB:  fTarget := 0.0;
END_CASE
END_FUNCTION_BLOCK
