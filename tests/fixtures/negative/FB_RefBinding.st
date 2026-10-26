// 'REF=' binds a reference; it compares nothing, so CP8 and CP28 stay silent.
// The bound members sit behind pragma lines, as in the library that showed it.
FUNCTION_BLOCK FB_RefBinding
VAR_OUTPUT
    tActive : TIME;
    fActive : LREAL;
END_VAR
VAR
    {attribute 'hide'}
    tSlow : TIME := T#5S;
    {attribute 'hide'}
    fGain : LREAL := 1.5;
    rTime : REFERENCE TO TIME;
    rGain : REFERENCE TO LREAL;
END_VAR
rTime REF= tSlow;
rGain REF= fGain;
IF __ISVALIDREF(rTime) AND __ISVALIDREF(rGain) THEN
    tActive := rTime;
    fActive := rGain;
END_IF
END_FUNCTION_BLOCK
