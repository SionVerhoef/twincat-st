// X12 stays silent on two guards TcOpen calls its task timers in: one entered
// whenever the timer's input drops ('... OR NOT bIn'), so the call there resets it,
// and one that only checks the reference the preset is read through. CP24 stays
// silent on a variable XAE declared for a UML state chart, which only the chart uses.
FUNCTION_BLOCK FB_GuardedTimer
VAR_INPUT
    bIn         : BOOL;
    bUseTimeout : BOOL;
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
    {attribute 'hide'}
    fbTimer : TON;
    {attribute 'hide'}
    fbInfo : TON;
    {attribute 'implicit_state_chart_struct' := ''}
    UML_SC_Main : _UML_SC_0123456789abcdef0123456789abcdef;
    rCfg : REFERENCE TO ST_TimerCfg;
END_VAR
rCfg REF= refCfg;
IF bUseTimeout OR NOT bIn THEN
    fbTimer(IN := bIn, PT := tTimeout);
END_IF
IF __ISVALIDREF(rCfg) THEN
    fbInfo(IN := bIn, PT := rCfg.tInfo);
END_IF
bTimedOut := fbTimer.Q;
bInfo := fbInfo.Q;
END_FUNCTION_BLOCK
