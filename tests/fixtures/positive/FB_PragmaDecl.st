// A declaration behind a pragma line is a declaration. The parser used to drop
// each one, so no rule saw it. nHidden is never used (CP24, reported on its own
// line, not the pragma's); nStep is marked TcRetain and steps its CASE (X13).
FUNCTION_BLOCK FB_PragmaDecl
VAR_INPUT
    bStart : BOOL;
END_VAR
VAR_OUTPUT
    bError : BOOL;
END_VAR
VAR
    {attribute 'hide'}
    nHidden : INT;
    {attribute 'TcRetain'}
    nStep : INT;
END_VAR
CASE nStep OF
    0:  IF bStart THEN nStep := 10; END_IF
    10: IF NOT bStart THEN nStep := 0; END_IF
    99: bError := TRUE;
        IF NOT bStart THEN bError := FALSE; nStep := 0; END_IF
ELSE
    nStep := 99;
END_CASE
END_FUNCTION_BLOCK
