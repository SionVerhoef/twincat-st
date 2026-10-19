// CP24 must stay quiet on the abstract method's parameter: it has no body to use
// it in, by design. The concrete method's parameter is used and also stays quiet.
FUNCTION_BLOCK ABSTRACT FB_AbstractHook
VAR_OUTPUT
    nLast : INT;
END_VAR

METHOD ABSTRACT OnStep
VAR_INPUT
    nStep : INT;
END_VAR

METHOD Record
VAR_INPUT
    nValue : INT;
END_VAR
nLast := nValue;
