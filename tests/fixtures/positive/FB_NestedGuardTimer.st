// X12: neither guard leaves the timer alone. 'OR NOT bIn' nested under 'bEnable
// AND (...)' is never entered with bEnable FALSE, so fbTimer is never reset; and a
// reference check joined with a run flag is a state branch, not a reference guard.
FUNCTION_BLOCK FB_NestedGuardTimer
VAR_INPUT
    bEnable     : BOOL;
    bUseTimeout : BOOL;
    bIn         : BOOL;
    tTimeout    : TIME;
END_VAR
VAR_IN_OUT
    refCfg : ST_TimerCfg;
END_VAR
VAR_OUTPUT
    bTimedOut : BOOL;
    bInfo     : BOOL;
END_VAR
VAR
    fbTimer : TON;
    fbCheck : TON;
    rCfg    : REFERENCE TO ST_TimerCfg;
END_VAR
rCfg REF= refCfg;
IF bEnable AND (bUseTimeout OR NOT bIn) THEN
    fbTimer(IN := bIn, PT := tTimeout);
END_IF
IF __ISVALIDREF(rCfg) AND bEnable THEN
    fbCheck(IN := bIn, PT := rCfg.tInfo);
END_IF
bTimedOut := fbTimer.Q;
bInfo := fbCheck.Q;
END_FUNCTION_BLOCK
