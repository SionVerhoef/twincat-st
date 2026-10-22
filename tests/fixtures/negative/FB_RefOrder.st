// E3: an ordering comparison through a REFERENCE TO, or through a dereferenced
// pointer, is on the values behind them, not on addresses. A reference is
// dereferenced implicitly and p^ is the value, so none of these is E3. Field
// round 4 reported 'ist_Zone.fEnd <= ist_Zone.fStart' (two LREAL members read
// through a REFERENCE TO a zone struct) as high, twice, on a production project.
FUNCTION_BLOCK FB_RefOrder
VAR_INPUT
    ist_Zone : REFERENCE TO ST_Zone;    // fStart, fEnd : LREAL [mm]
    refA : REFERENCE TO LREAL;
    refB : REFERENCE TO LREAL;
    pZone : POINTER TO ST_Zone;
    pA : POINTER TO LREAL;
    pB : POINTER TO LREAL;
END_VAR
VAR_OUTPUT
    bEmpty : BOOL;
    bBelow : BOOL;
    bPtrEmpty : BOOL;
    bPtrBelow : BOOL;
END_VAR
// Members read through a reference: the shape the field reported.
IF __ISVALIDREF(ist_Zone) THEN
    bEmpty := ist_Zone.fEnd <= ist_Zone.fStart;
END_IF
// Two references compared directly: still the values.
IF __ISVALIDREF(refA) THEN
    IF __ISVALIDREF(refB) THEN
        bBelow := refA < refB;
    END_IF
END_IF
// Members and values read through a dereferenced pointer.
IF pZone <> 0 THEN
    bPtrEmpty := pZone^.fEnd <= pZone^.fStart;
END_IF
IF pA <> 0 THEN
    IF pB <> 0 THEN
        bPtrBelow := pA^ < pB^;
    END_IF
END_IF
END_FUNCTION_BLOCK
