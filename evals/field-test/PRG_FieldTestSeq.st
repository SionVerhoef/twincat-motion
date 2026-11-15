// PRG_FieldTestSeq: runs sections C, D and E of the field test (evals/field-test/README.md)
// as step chains, and writes what happened to a log the agent copies into the results.
//
// Two objects. Use them in the same THROWAWAY project as PRG_FieldTest, simulated axes only.
// 1. Add a FUNCTION_BLOCK FB_FieldTestLog and a PROGRAM PRG_FieldTestSeq (Structured
//    Text). Paste each DECLARATION part into the declaration pane and each IMPLEMENTATION
//    part into the code pane.
// 2. Needs PRG_FieldTest from PRG_FieldTest.st, and the patched copy of PRG_AxisExample
//    from README B3 (its commands and parameters moved to VAR_INPUT). Without
//    Tc2_MC2_Camming, delete every line that ends in // CAM, here and in PRG_FieldTest;
//    E5 then logs "no such step" and is skipped, and E6 starts at MC_GearIn.
// 3. Call order in MAIN: PRG_FieldTestSeq(); PRG_FieldTest(); PRG_AxisExample();
//    The sequencer reads the outputs of the previous cycle and writes the inputs of this one.
// 4. Online: write sRun := 'C3' to run one check, or 'C' to run C1 to C8 in order (also
//    'D', 'E', 'D2', ...). A line "WAIT ..." asks the operator to do something in XAE:
//    do it, then write bContinue := TRUE. bAbort := TRUE stops and releases every command.
// 5. Read fbLog.aLog[1..fbLog.nLines]. Each line is "<ms> <check> <text> [value]": ms since
//    the PLC started, codes in hex. Lines "M 16#... ^16#..." are the section's FB-flag mask
//    and the bits that changed; the bit legend is below. "HomingState n" lines follow
//    Axis.NcToPlc.HomingState. bClearLog := TRUE empties the log (1000 lines).
//
// Every check first settles its section: default parameters, axes enabled and reset,
// slave decoupled, axes stopped, PRG_FieldTest's results cleared. A step that waits longer
// than tStepTimeout (or its own limit) logs TIMEOUT, releases every command, settles
// (which halts the axes) and stops; bAbort does the same.
// Moves start from where the axis stands: C1, C7 and C8 put their targets relative to it.
//
// Written for TwinCAT 4024.55 with Tc2_MC2 3.3.59; not yet built. Fix compile errors on
// site and record them as a diff (README B2).
//
// Mask bits. C (PRG_FieldTest, Axis1):
//   0 fbPower1.Status  1 Axis1 Error  2 Axis1 ErrorStop  3 Axis1 Homed
//   4 Axis1 MotionCommandsLocked  5 Axis1 NotMoving
//   6..9 fbMoveA Busy, Done, Error, CommandAborted   10..13 fbMoveB the same
//   14..17 fbMoveVelo Busy, InVelocity, Error, CommandAborted
//   18..20 fbHalt1 Busy, Done, Error   21..23 fbStop1 Busy, Done, Error
//   24..27 fbHome1 Busy, Done, Error, CommandAborted
//   28, 29 fbSetPos1 Done, Error   30, 31 fbReset1 Done, Error
// D (PRG_AxisExample, its Axis1):
//   0..4 fbAxis bReady, bBusy, bDone, bCommandAborted, bError   5 bAccepted
//   6..9 fbHomePlc bBusy, bDone, bError, bHomed   10..12 fbHomeNc bBusy, bDone, bError
//   13 bHomed  14 bError  15 Axis1 Homed  16 Axis1 Error  17 Axis1 NotMoving
//   18 bRefSwitch  19 bCamNc  20 Axis1 HomingBusy
// E (PRG_FieldTest, Axis1 master, Axis2 slave):
//   0, 1 fbPower1/2.Status  2, 3 Axis1/2 Error  4 Axis2 Coupled  5 Axis2 ProtectedMode
//   6 Axis2 NotMoving  7 Axis2 ContinuousMotion
//   8..11 fbGearIn Busy, InGear, Error, CommandAborted   12, 13 fbGearOut Done, Error
//   14, 15 fbGearInDyn InGear, Error   16..19 fbMoveSlave Busy, Done, Error, CommandAborted
//   20..22 fbHalt2 Busy, Done, Error   23..25 fbPhasing Busy, Done, Error
//   26, 27 fbCamSelect Done, Error   28, 29 fbCamIn InSync, Error   30 fbCamOut Done
//   31 fbMoveVelo InVelocity (master)

// ==== FB_FieldTestLog DECLARATION ====
FUNCTION_BLOCK FB_FieldTestLog
VAR_INPUT
    sTag    : STRING(8);    // the running check, e.g. 'C3'; set by the caller
    sText   : STRING(80);   // one call with sText set = one line
    nFmt    : INT;          // value after the text: 0 none, 1 hex, 2 LREAL, 3 BOOL,
                            // 4 nVal and nVal2 as 8-digit hex (the mask), 5 decimal
    nVal    : UDINT;
    nVal2   : UDINT;
    fVal    : LREAL;
    bVal    : BOOL;
    bClear  : BOOL;         // empty the log
END_VAR
VAR_OUTPUT
    nLines  : INT;          // lines written
    bFull   : BOOL;         // the last line says so; nothing more is logged
END_VAR
VAR
    aLog    : ARRAY[1..1000] OF STRING(160);
    fbClock : TON;          // free-running millisecond clock
    sLine   : STRING(255);
    sValue  : STRING(60);
    sHex    : STRING(12);
    dwHex   : DWORD;
    nDigits : INT;
    nNib    : INT;
    i       : INT;
    k       : INT;
END_VAR
VAR CONSTANT
    cDigits : STRING(16) := '0123456789ABCDEF';
END_VAR
// ==== FB_FieldTestLog END DECLARATION ====

// ==== FB_FieldTestLog IMPLEMENTATION ====
fbClock(IN := TRUE, PT := T#24D);

IF bClear THEN
    bClear := FALSE;
    FOR i := 1 TO 1000 DO
        aLog[i] := '';
    END_FOR
    nLines := 0;
    bFull := FALSE;
END_IF

IF sText <> '' THEN
    sValue := '';
    CASE nFmt OF
    1, 4:
        FOR k := 1 TO 2 DO
            IF k = 1 THEN
                dwHex := UDINT_TO_DWORD(nVal);
            ELSE
                dwHex := UDINT_TO_DWORD(nVal2);
            END_IF
            nDigits := 4;
            IF (nFmt = 4) OR (dwHex > 16#FFFF) THEN
                nDigits := 8;
            END_IF
            sHex := '16#';
            FOR i := nDigits - 1 TO 0 BY -1 DO
                nNib := DWORD_TO_INT(SHR(dwHex, i * 4) AND 16#F);
                sHex := CONCAT(sHex, MID(cDigits, 1, nNib + 1));
            END_FOR
            IF k = 1 THEN
                sValue := sHex;
            ELSIF nFmt = 4 THEN
                sValue := CONCAT(CONCAT(sValue, ' ^'), sHex);
            END_IF
        END_FOR
    2:
        sValue := LREAL_TO_STRING(fVal);
    3:
        sValue := BOOL_TO_STRING(bVal);
    5:
        sValue := UDINT_TO_STRING(nVal);
    ELSE
        sValue := '';                                  // 0: text only
    END_CASE

    sLine := CONCAT(UDINT_TO_STRING(TIME_TO_UDINT(fbClock.ET)), ' ');
    sLine := CONCAT(sLine, sTag);
    sLine := CONCAT(sLine, ' ');
    sLine := CONCAT(sLine, sText);
    IF nFmt <> 0 THEN
        sLine := CONCAT(sLine, ' ');
        sLine := CONCAT(sLine, sValue);
    END_IF

    IF nLines < 999 THEN
        nLines := nLines + 1;
        aLog[nLines] := sLine;
    ELSIF NOT bFull THEN
        bFull := TRUE;
        nLines := 1000;
        aLog[1000] := 'LOG FULL: copy the log, then bClearLog := TRUE';
    END_IF

    // Inputs keep their value between calls: reset them for the next line.
    sText := '';
    nFmt := 0;
    nVal := 0;
    nVal2 := 0;
    fVal := 0.0;
    bVal := FALSE;
END_IF
// ==== FB_FieldTestLog END IMPLEMENTATION ====

// ==== PRG_FieldTestSeq DECLARATION ====
PROGRAM PRG_FieldTestSeq
VAR_INPUT
    sRun         : STRING(4);    // 'C3' runs C3; 'C' runs C1..C8. Read and cleared.
    bContinue    : BOOL;         // the operator did what the last WAIT line asked
    bAbort       : BOOL;         // stop now, release every command
    bClearLog    : BOOL;
    tStepTimeout : TIME := T#30S;
END_VAR
VAR
    fbLog        : FB_FieldTestLog;

    // Step numbers: 1000 + 100 * check + n for C, 2000 + ... for D, 3000 + ... for E.
    // x900..x999 is the section's settle chain; it returns to nRet.
    nStep        : INT;
    nStepLast    : INT := -1;
    bEntry       : BOOL;         // TRUE in the first cycle of a step
    tonStep      : TON;          // time in this step; ET also times the waits
    tStepMax     : TIME;         // a step may raise its own limit on entry
    bNoTimeout   : BOOL;         // set by WAIT steps: the operator takes as long as needed
    nSection     : INT;          // 1 C, 2 D, 3 E
    nCheck       : INT;
    bRunAll      : BOOL;
    nRet         : INT;
    bCheckDone   : BOOL;
    bRelease     : BOOL;         // write every command BOOL FALSE, after the CASE
    bDefaults    : BOOL;         // write every parameter back to its default, after the CASE
    sSec         : STRING(1);
    nNum         : INT;
    nIdx         : INT;          // run counter inside a check
    fStart       : LREAL;
    fDiff0       : LREAL;        // E6: slave minus master before phasing
    fPeak        : LREAL;
    dwMask       : DWORD;
    dwMaskPrev   : DWORD;
    bMaskFirst   : BOOL;         // log the whole mask once at the start of a run
    nHs          : UDINT;
    nHsPrev      : UDINT;
    nRetry       : INT;          // settle C: MC_Reset attempts

    aSecName     : ARRAY[1..3] OF STRING(1) := ['C', 'D', 'E'];
    aLastCheck   : ARRAY[1..3] OF INT := [8, 4, 7];
    aC3Dec       : ARRAY[1..4] OF LREAL := [500.0, 500.0, 200.0, 500.0];
    aC3Halt      : ARRAY[1..4] OF LREAL := [500.0, 0.0, 0.0, 100.0];
    aC3Run       : ARRAY[1..4] OF STRING(1) := ['a', 'b', 'c', 'd'];
    aE3Dec       : ARRAY[1..2] OF LREAL := [500.0, 200.0];
END_VAR
VAR CONSTANT
    cHex         : INT := 1;
    cReal        : INT := 2;
    cBool        : INT := 3;
    cMask        : INT := 4;
    cDec         : INT := 5;
END_VAR
// ==== PRG_FieldTestSeq END DECLARATION ====

// ==== PRG_FieldTestSeq IMPLEMENTATION ====
// ---- 1. Operator inputs
IF bClearLog THEN
    bClearLog := FALSE;
    fbLog(bClear := TRUE);
END_IF

IF bAbort THEN
    bAbort := FALSE;
    IF nStep <> 0 THEN
        fbLog(sText := 'ABORT by operator in step', nFmt := cDec, nVal := INT_TO_UDINT(nStep));
    END_IF
    bRunAll := FALSE;
    bRelease := TRUE;
    IF nStep <> 0 AND (nStep MOD 1000) < 900 THEN
        nRet := 0;
        nStep := 1000 * nSection + 900;               // settle: halts the axes, then idle
    ELSE
        nStep := 0;                                    // abort in settle: stop at once
    END_IF
END_IF

IF sRun <> '' THEN
    IF nStep <> 0 THEN
        fbLog(sText := 'busy: ignored, write bAbort first');
    ELSE
        sSec := LEFT(sRun, 1);
        IF LEN(sRun) > 1 THEN
            nNum := STRING_TO_INT(RIGHT(sRun, LEN(sRun) - 1));
            bRunAll := FALSE;
        ELSE
            nNum := 1;
            bRunAll := TRUE;
        END_IF
        nSection := 0;
        IF sSec = 'C' OR sSec = 'c' THEN
            nSection := 1;
        ELSIF sSec = 'D' OR sSec = 'd' THEN
            nSection := 2;
        ELSIF sSec = 'E' OR sSec = 'e' THEN
            nSection := 3;
        END_IF
        IF nSection = 0 OR nNum < 1 OR nNum > aLastCheck[MAX(nSection, 1)] THEN
            fbLog.sTag := '';
            fbLog(sText := CONCAT('unknown check: ', sRun));
            bRunAll := FALSE;
        ELSE
            nCheck := nNum;
            fbLog.sTag := CONCAT(aSecName[nSection], INT_TO_STRING(nCheck));
            fbLog(sText := 'START');
            nRet := 1000 * nSection + 100 * nCheck;
            nStep := 1000 * nSection + 900;
            bMaskFirst := TRUE;
            nHsPrev := 16#FFFFFFFF;
        END_IF
    END_IF
    sRun := '';
END_IF

// ---- 2. Step bookkeeping
bEntry := nStep <> nStepLast;
nStepLast := nStep;
IF bEntry THEN
    bNoTimeout := FALSE;
    tStepMax := tStepTimeout;
END_IF

// ---- 3. Section C: one simulated axis, PRG_FieldTest.Axis1
IF nStep >= 1000 AND nStep < 2000 THEN
    CASE nStep OF
    // -- settle: defaults, enabled, no error, standing still
    1900:
        IF bEntry THEN
            bDefaults := TRUE;
            PRG_FieldTest.bClear := TRUE;
            PRG_FieldTest.bEnable1 := TRUE;
        ELSIF PRG_FieldTest.fbPower1.Status OR PRG_FieldTest.Axis1.Status.Error THEN
            nStep := 1901;
        END_IF
    1901:
        IF PRG_FieldTest.Axis1.Status.MotionCommandsLocked OR PRG_FieldTest.fbStop1.Busy THEN
            ;                                          // MC_Stop still releasing (C2)
        ELSIF PRG_FieldTest.Axis1.Status.Error THEN
            PRG_FieldTest.bReset1 := TRUE;
            nStep := 1902;
        ELSIF NOT PRG_FieldTest.Axis1.Status.NotMoving THEN
            PRG_FieldTest.fHaltDec1 := 500.0;
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 1903;
        ELSE
            nStep := 1904;
        END_IF
    1902:
        IF PRG_FieldTest.fbReset1.Done OR PRG_FieldTest.fbReset1.Error THEN
            PRG_FieldTest.bReset1 := FALSE;
            IF PRG_FieldTest.fbReset1.Error THEN
                fbLog(sText := 'settle: MC_Reset failed', nFmt := cHex,
                      nVal := PRG_FieldTest.fbReset1.ErrorID);
                nStep := 1904;
            ELSIF nRetry < 3 THEN
                nRetry := nRetry + 1;
                nStep := 1900;
            ELSE
                fbLog(sText := 'settle: axis error stays after 3 resets');
                nStep := 1904;
            END_IF
        END_IF
    1903:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            nStep := 1904;
        END_IF
    1904:
        nRetry := 0;
        PRG_FieldTest.bClear := TRUE;
        nStep := nRet;

    // -- C1: MC_Power with only Enable
    1100:
        IF bEntry THEN
            PRG_FieldTest.bEnPos1 := FALSE;
            PRG_FieldTest.bEnNeg1 := FALSE;
            fStart := PRG_FieldTest.Axis1.NcToPlc.ActPos;
            PRG_FieldTest.fPosA := fStart + 500.0;     // positive
            PRG_FieldTest.fPosB := fStart - 500.0;     // negative
        ELSIF tonStep.ET >= T#500MS THEN
            fbLog(sText := 'Status, Enable only', nFmt := cBool,
                  bVal := PRG_FieldTest.fbPower1.Status);
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1101;
        END_IF
    1101:
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error OR tonStep.ET >= T#2S THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'move+ no enables: nErrMoveA', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            fbLog(sText := 'ErrorStop', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.ErrorStop);
            fbLog(sText := 'bStatusDropped1', nFmt := cBool,
                  bVal := PRG_FieldTest.bStatusDropped1);
            fbLog(sText := 'fbMoveA.Busy (moving anyway?)', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveA.Busy);
            nStep := 1102;
        END_IF
    1102:
        IF bEntry THEN
            PRG_FieldTest.bEnPos1 := TRUE;
            PRG_FieldTest.bClear := TRUE;
        ELSIF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1103;
        END_IF
    1103:
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'move+ Enable_Positive only, no reset: Done', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveA.Done);
            fbLog(sText := 'nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            nStep := 1104;
        END_IF
    1104:
        IF bEntry THEN
            PRG_FieldTest.bClear := TRUE;
        ELSIF tonStep.ET >= T#200MS THEN
            PRG_FieldTest.bMoveB := TRUE;
            nStep := 1105;
        END_IF
    1105:
        IF PRG_FieldTest.fbMoveB.Done OR PRG_FieldTest.fbMoveB.Error OR tonStep.ET >= T#2S THEN
            PRG_FieldTest.bMoveB := FALSE;
            fbLog(sText := 'move- Enable_Positive only: nErrMoveB', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrMoveB);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            fbLog(sText := 'ErrorStop', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.ErrorStop);
            fbLog(sText := 'fbMoveB.Busy (moving anyway?)', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveB.Busy);
            bCheckDone := TRUE;
        END_IF

    // -- C2: MC_Stop locks the axis; then MC_Reset while the stop is held
    1200, 1210:
        PRG_FieldTest.bMoveVelo := TRUE;
        nStep := nStep + 1;
    1201, 1211:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            PRG_FieldTest.bStop1 := TRUE;
            nStep := nStep + 1;
        END_IF
    1202:
        IF PRG_FieldTest.fbStop1.Done OR PRG_FieldTest.fbStop1.Error THEN
            fbLog(sText := 'held: fbStop1.Done', nFmt := cBool, bVal := PRG_FieldTest.fbStop1.Done);
            fbLog(sText := 'held: fbStop1.Busy', nFmt := cBool, bVal := PRG_FieldTest.fbStop1.Busy);
            fbLog(sText := 'held: fbStop1.Active', nFmt := cBool,
                  bVal := PRG_FieldTest.fbStop1.Active);
            fbLog(sText := 'held: MotionCommandsLocked', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.MotionCommandsLocked);
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1203;
        END_IF
    1203:
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error OR tonStep.ET >= T#1S THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'move while stop held: nErrMoveA', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrMoveA);
            PRG_FieldTest.bStop1 := FALSE;
            nStep := 1204;
        END_IF
    1204:
        IF tonStep.ET >= T#100MS AND NOT PRG_FieldTest.bStopCounting THEN
            fbLog(sText := 'released: nStopRelease (PLC cycles)', nFmt := cDec,
                  nVal := PRG_FieldTest.nStopRelease);
            fbLog(sText := 'released: MotionCommandsLocked', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.MotionCommandsLocked);
            PRG_FieldTest.bClear := TRUE;
            nStep := 1210;
        END_IF
    1212:
        IF PRG_FieldTest.fbStop1.Done OR PRG_FieldTest.fbStop1.Error THEN
            PRG_FieldTest.bReset1 := TRUE;
            nStep := 1213;
        END_IF
    1213:
        IF PRG_FieldTest.fbReset1.Done OR PRG_FieldTest.fbReset1.Error THEN
            PRG_FieldTest.bReset1 := FALSE;
            fbLog(sText := 'reset while stop held: nErrReset1', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrReset1);
            fbLog(sText := 'after reset: MotionCommandsLocked', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.MotionCommandsLocked);
            fbLog(sText := 'after reset: fbStop1.Busy', nFmt := cBool,
                  bVal := PRG_FieldTest.fbStop1.Busy);
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1214;
        END_IF
    1214:
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error
           OR PRG_FieldTest.fbMoveA.CommandAborted OR tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'move after reset, stop still held: Busy', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveA.Busy);
            fbLog(sText := 'nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis1.NcToPlc.SetVelo);
            PRG_FieldTest.bStop1 := FALSE;
            bCheckDone := TRUE;
        END_IF

    // -- C3: MC_Halt with Deceleration 0, runs a to d
    1300:
        nIdx := 1;
        fbLog(sText := 'record the axis default deceleration and jerk from XAE');
        nStep := 1301;
    1301:
        PRG_FieldTest.fVelo := 500.0;
        PRG_FieldTest.fDec := aC3Dec[nIdx];
        PRG_FieldTest.bMoveVelo := TRUE;
        nStep := 1302;
    1302:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            PRG_FieldTest.fHaltDec1 := aC3Halt[nIdx];
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 1303;
        END_IF
    1303:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            fbLog(sText := CONCAT(CONCAT('run ', aC3Run[nIdx]), ' fDec'), nFmt := cReal,
                  fVal := aC3Dec[nIdx]);
            fbLog(sText := CONCAT(CONCAT('run ', aC3Run[nIdx]), ' fHaltDec1'), nFmt := cReal,
                  fVal := aC3Halt[nIdx]);
            fbLog(sText := CONCAT(CONCAT('run ', aC3Run[nIdx]), ' fPeakDecel1'), nFmt := cReal,
                  fVal := PRG_FieldTest.fPeakDecel1);
            fbLog(sText := 'nErrHalt1', nFmt := cHex, nVal := PRG_FieldTest.nErrHalt1);
            nIdx := nIdx + 1;
            IF nIdx <= 4 THEN
                nStep := 1301;
            ELSE
                bCheckDone := TRUE;
            END_IF
        END_IF

    // -- C4: which commands set the NC's homed state
    1400:
        nIdx := 1;
        nStep := 1401;
    1401:
        CASE nIdx OF
        1, 6:
            PRG_FieldTest.eHomeMode1 := MC_HomingMode.MC_ResetCalibration;
            PRG_FieldTest.bHome1 := TRUE;
        2:
            PRG_FieldTest.fSetPos1 := 10.0;
            PRG_FieldTest.bSetPos1 := TRUE;
        3:
            PRG_FieldTest.eHomeMode1 := MC_HomingMode.MC_Direct;
            PRG_FieldTest.fHomePos1 := 20.0;
            PRG_FieldTest.bHome1 := TRUE;
        4:
            PRG_FieldTest.eHomeMode1 := MC_HomingMode.MC_ForceCalibration;
            PRG_FieldTest.bHome1 := TRUE;
        5:
            PRG_FieldTest.fSetPos1 := 30.0;            // MC_SetPosition on a homed axis
            PRG_FieldTest.bSetPos1 := TRUE;
        END_CASE
        nStep := 1402;
    1402:
        IF PRG_FieldTest.fbHome1.Done OR PRG_FieldTest.fbHome1.Error
           OR PRG_FieldTest.fbSetPos1.Done OR PRG_FieldTest.fbSetPos1.Error THEN
            PRG_FieldTest.bHome1 := FALSE;
            PRG_FieldTest.bSetPos1 := FALSE;
            nStep := 1403;
        END_IF
    1403:
        // one cycle later, so Status and ActPos show the command's result
        CASE nIdx OF
        1: fbLog(sText := '1 MC_ResetCalibration: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        2: fbLog(sText := '2 MC_SetPosition 10: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        3: fbLog(sText := '3 MC_Direct 20: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        4: fbLog(sText := '4 MC_ForceCalibration: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        5: fbLog(sText := '5 MC_SetPosition 30 on homed axis: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        6: fbLog(sText := '6 MC_ResetCalibration: Homed', nFmt := cBool,
                 bVal := PRG_FieldTest.Axis1.Status.Homed);
        END_CASE
        fbLog(sText := 'ActPos', nFmt := cReal, fVal := PRG_FieldTest.Axis1.NcToPlc.ActPos);
        fbLog(sText := 'nErrHome1', nFmt := cHex, nVal := PRG_FieldTest.nErrHome1);
        fbLog(sText := 'nErrSetPos1', nFmt := cHex, nVal := PRG_FieldTest.nErrSetPos1);
        nIdx := nIdx + 1;
        IF nIdx <= 6 THEN
            nStep := 1401;
        ELSE
            bCheckDone := TRUE;
        END_IF

    // -- C5: default homing, then MC_Halt during MC_Home, then homing again without reset
    1500:
        IF bEntry THEN
            bContinue := FALSE;
            fbLog(sText := 'WAIT start Scope (HomingState, ActPos, SetPos, bCam1, fbHome1), bContinue');
        END_IF
        bNoTimeout := TRUE;
        IF bContinue THEN
            bContinue := FALSE;
            nStep := 1501;
        END_IF
    1501:
        PRG_FieldTest.eHomeMode1 := MC_HomingMode.MC_DefaultHoming;
        PRG_FieldTest.bCam1 := FALSE;
        PRG_FieldTest.bHome1 := TRUE;                  // held until Done or Error
        nStep := 1502;
    1502:
        IF tonStep.ET >= T#2S THEN                     // searching for the cam
            fbLog(sText := 'cam on, SetVelo', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis1.NcToPlc.SetVelo);
            PRG_FieldTest.bCam1 := TRUE;
            nStep := 1503;
        END_IF
    1503:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'cam off, SetVelo', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis1.NcToPlc.SetVelo);
            PRG_FieldTest.bCam1 := FALSE;
            nStep := 1504;
        END_IF
    1504:
        IF PRG_FieldTest.fbHome1.Done OR PRG_FieldTest.fbHome1.Error THEN
            PRG_FieldTest.bHome1 := FALSE;
            fbLog(sText := 'homing Done', nFmt := cBool, bVal := PRG_FieldTest.fbHome1.Done);
            fbLog(sText := 'nErrHome1', nFmt := cHex, nVal := PRG_FieldTest.nErrHome1);
            fbLog(sText := 'ActPos', nFmt := cReal, fVal := PRG_FieldTest.Axis1.NcToPlc.ActPos);
            PRG_FieldTest.bClear := TRUE;
            nStep := 1505;
        END_IF
    1505:
        IF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bCam1 := FALSE;
            PRG_FieldTest.bHome1 := TRUE;
            nStep := 1506;
        END_IF
    1506:
        IF tonStep.ET >= T#2S THEN                     // searching: halt it
            PRG_FieldTest.fHaltDec1 := 500.0;
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 1507;
        END_IF
    1507:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error OR tonStep.ET >= T#5S THEN
            fbLog(sText := 'halt during homing: NotMoving', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.NotMoving);
            fbLog(sText := 'nErrHome1', nFmt := cHex, nVal := PRG_FieldTest.nErrHome1);
            fbLog(sText := 'bAbortedHome1', nFmt := cBool, bVal := PRG_FieldTest.bAbortedHome1);
            fbLog(sText := 'nErrHalt1', nFmt := cHex, nVal := PRG_FieldTest.nErrHalt1);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            fbLog(sText := 'HomingState', nFmt := cDec,
                  nVal := PRG_FieldTest.Axis1.NcToPlc.HomingState);
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            PRG_FieldTest.bHome1 := FALSE;
            PRG_FieldTest.bClear := TRUE;
            nStep := 1508;
        END_IF
    1508:
        IF tonStep.ET >= T#500MS THEN                  // homing again, no MC_Reset
            PRG_FieldTest.bHome1 := TRUE;
            nStep := 1509;
        END_IF
    1509:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'restart without reset: fbHome1.Busy', nFmt := cBool,
                  bVal := PRG_FieldTest.fbHome1.Busy);
            fbLog(sText := 'nErrHome1', nFmt := cHex, nVal := PRG_FieldTest.nErrHome1);
            PRG_FieldTest.bCam1 := TRUE;
            nStep := 1510;
        END_IF
    1510:
        IF tonStep.ET >= T#1S THEN
            PRG_FieldTest.bCam1 := FALSE;
            nStep := 1511;
        END_IF
    1511:
        IF PRG_FieldTest.fbHome1.Done OR PRG_FieldTest.fbHome1.Error
           OR NOT PRG_FieldTest.fbHome1.Busy THEN
            PRG_FieldTest.bHome1 := FALSE;
            fbLog(sText := 'second homing Done', nFmt := cBool,
                  bVal := PRG_FieldTest.fbHome1.Done);
            fbLog(sText := 'nErrHome1', nFmt := cHex, nVal := PRG_FieldTest.nErrHome1);
            bCheckDone := TRUE;
        END_IF

    // -- C6: override
    1600:
        PRG_FieldTest.bMoveVelo := TRUE;               // held TRUE on purpose
        nStep := 1601;
    1601:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            nIdx := 1;
            PRG_FieldTest.fOverride1 := 50.0;
            nStep := 1602;
        END_IF
    1602:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'override', nFmt := cReal, fVal := PRG_FieldTest.fOverride1);
            fbLog(sText := 'InVelocity', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveVelo.InVelocity);
            fbLog(sText := 'Busy', nFmt := cBool, bVal := PRG_FieldTest.fbMoveVelo.Busy);
            fbLog(sText := 'bAbortedVelo', nFmt := cBool, bVal := PRG_FieldTest.bAbortedVelo);
            fbLog(sText := 'SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis1.NcToPlc.SetVelo);
            nIdx := nIdx + 1;
            CASE nIdx OF
            2: PRG_FieldTest.fOverride1 := 0.0;
            3: PRG_FieldTest.fOverride1 := 100.0;
            END_CASE
            IF nIdx <= 3 THEN
                nStep := 1603;                         // re-enter 1602 for the next value
            ELSE
                PRG_FieldTest.fOverride1 := 0.0;
                PRG_FieldTest.bMoveVelo := FALSE;
                nStep := 1604;
            END_IF
        END_IF
    1603:
        nStep := 1602;
    1604:
        IF tonStep.ET >= T#1S THEN                     // override 0, axis standing
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1605;
        END_IF
    1605:
        PRG_FieldTest.bMoveA := FALSE;                 // a pulse
        nStep := 1606;
    1606:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'override 0, MoveA: Busy', nFmt := cBool,
                  bVal := PRG_FieldTest.fbMoveA.Busy);
            fbLog(sText := 'Done', nFmt := cBool, bVal := PRG_FieldTest.fbMoveA.Done);
            fbLog(sText := 'nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'NotMoving', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.NotMoving);
            PRG_FieldTest.fOverride1 := 100.0;
            bCheckDone := TRUE;
        END_IF

    // -- C7: zero velocity, zero acceleration
    1700:
        PRG_FieldTest.fPosA := PRG_FieldTest.Axis1.NcToPlc.ActPos + 300.0;
        PRG_FieldTest.fVelo := 0.0;
        PRG_FieldTest.bMoveA := TRUE;
        nStep := 1701;
    1701:
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error OR tonStep.ET >= T#2S THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'velocity 0: nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            fbLog(sText := 'ErrorStop', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis1.Status.ErrorStop);
            nStep := 1702;
        END_IF
    1702:
        IF PRG_FieldTest.Axis1.Status.Error THEN
            PRG_FieldTest.bReset1 := TRUE;
        END_IF
        nStep := 1703;
    1703:
        IF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bReset1 := FALSE;
            PRG_FieldTest.bClear := TRUE;
            PRG_FieldTest.fVelo := 100.0;
            PRG_FieldTest.fAcc := 0.0;
            fPeak := 0.0;
            PRG_FieldTest.bMoveA := TRUE;
            nStep := 1704;
        END_IF
    1704:
        IF PRG_FieldTest.fbMoveA.Busy AND ABS(PRG_FieldTest.Axis1.NcToPlc.SetAcc) > fPeak THEN
            fPeak := ABS(PRG_FieldTest.Axis1.NcToPlc.SetAcc);
        END_IF
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error THEN
            PRG_FieldTest.bMoveA := FALSE;
            fbLog(sText := 'acceleration 0: Done', nFmt := cBool, bVal := PRG_FieldTest.fbMoveA.Done);
            fbLog(sText := 'nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'peak |SetAcc|, compare the axis defaults', nFmt := cReal, fVal := fPeak);
            bCheckDone := TRUE;
        END_IF

    // -- C8: retargeting a running move
    1800:
        fStart := PRG_FieldTest.Axis1.NcToPlc.ActPos;
        PRG_FieldTest.fPosA := fStart + 1000.0;
        PRG_FieldTest.fPosB := fStart + 400.0;
        PRG_FieldTest.bMoveA := TRUE;
        nStep := 1801;
    1801:
        IF tonStep.ET >= T#1S THEN
            PRG_FieldTest.bMoveA := FALSE;
            PRG_FieldTest.fPosA := fStart + 300.0;
            nStep := 1802;
        END_IF
    1802:
        PRG_FieldTest.bMoveA := TRUE;                  // second rising edge, A still busy
        nStep := 1803;
    1803:
        PRG_FieldTest.bMoveA := FALSE;
        fbLog(sText := 'second edge on busy A: Error', nFmt := cBool,
              bVal := PRG_FieldTest.fbMoveA.Error);
        fbLog(sText := 'nErrMoveA', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveA);
        nStep := 1804;
    1804:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'A target now (SetPos - start, still rising?)', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis1.NcToPlc.SetPos - fStart);
            PRG_FieldTest.bMoveB := TRUE;              // second instance, to start + 400
            nStep := 1805;
        END_IF
    1805:
        IF PRG_FieldTest.fbMoveB.Done OR PRG_FieldTest.fbMoveB.Error THEN
            PRG_FieldTest.bMoveB := FALSE;
            fbLog(sText := 'end: ActPos - start', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis1.NcToPlc.ActPos - fStart);
            fbLog(sText := 'bAbortedA', nFmt := cBool, bVal := PRG_FieldTest.bAbortedA);
            fbLog(sText := 'nErrMoveA (second edge, latched)', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrMoveA);
            fbLog(sText := 'nErrMoveB', nFmt := cHex, nVal := PRG_FieldTest.nErrMoveB);
            fbLog(sText := 'nAxisErr1', nFmt := cHex, nVal := PRG_FieldTest.nAxisErr1);
            bCheckDone := TRUE;
        END_IF

    ELSE
        fbLog(sText := 'no such step', nFmt := cDec, nVal := INT_TO_UDINT(nStep));
        bCheckDone := TRUE;
    END_CASE

// ---- 4. Section D: the templates, PRG_AxisExample (patched copy, README B3)
ELSIF nStep >= 2000 AND nStep < 3000 THEN
    CASE nStep OF
    // -- settle: defaults, powered, no error, standing still
    2900:
        IF bEntry THEN
            bDefaults := TRUE;
            PRG_AxisExample.bPowerOn := TRUE;
        ELSIF PRG_AxisExample.fbAxis.bReady OR PRG_AxisExample.fbAxis.bError THEN
            nStep := 2901;
        END_IF
    2901:
        IF PRG_AxisExample.fbAxis.bError THEN
            PRG_AxisExample.bResetCmd := TRUE;
            nStep := 2902;
        ELSIF NOT PRG_AxisExample.Axis1.Status.NotMoving THEN
            PRG_AxisExample.bHaltCmd := TRUE;
            nStep := 2903;
        ELSE
            nStep := 2904;
        END_IF
    2902:
        PRG_AxisExample.bResetCmd := FALSE;
        IF tonStep.ET >= T#500MS THEN
            nStep := 2904;
        END_IF
    2903:
        PRG_AxisExample.bHaltCmd := FALSE;
        IF PRG_AxisExample.Axis1.Status.NotMoving THEN
            nStep := 2904;
        END_IF
    2904:
        nStep := nRet;

    // -- D1: power and reset
    2100:
        IF bEntry THEN
            PRG_AxisExample.bPowerOn := FALSE;
        ELSIF tonStep.ET >= T#500MS THEN
            PRG_AxisExample.bPowerOn := TRUE;
            nStep := 2101;
        END_IF
    2101:
        IF PRG_AxisExample.fbAxis.bReady OR PRG_AxisExample.fbAxis.bError THEN
            fbLog(sText := 'bReady', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bReady);
            PRG_AxisExample.bResetCmd := TRUE;
            nStep := 2102;
        END_IF
    2102:
        PRG_AxisExample.bResetCmd := FALSE;
        fbLog(sText := 'reset: bAccepted', nFmt := cBool, bVal := PRG_AxisExample.bAccepted);
        nStep := 2103;
    2103:
        IF tonStep.ET >= T#500MS THEN
            fbLog(sText := 'bReady', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bReady);
            fbLog(sText := 'bError', nFmt := cBool, bVal := PRG_AxisExample.bError);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.nErrorID);
            bCheckDone := TRUE;
        END_IF

    // -- D2: FB_HomePlc, runs 1 to 4
    2200:
        nIdx := 1;
        PRG_AxisExample.stHomePlc.bMarkNcHomed := FALSE;
        nStep := 2201;
    2201:                                              // runs 1, 2 and 3 start here
        fbLog(sText := 'run, start ActPos', nFmt := cReal,
              fVal := PRG_AxisExample.Axis1.NcToPlc.ActPos);
        fbLog(sText := 'run number', nFmt := cDec, nVal := INT_TO_UDINT(nIdx));
        PRG_AxisExample.bHomeCmd := TRUE;              // held until done or error
        nStep := 2202;
    2202:
        tStepMax := T#300S;                            // 5 mm/s search over the whole stroke
        IF PRG_AxisExample.fbHomePlc.bDone OR PRG_AxisExample.fbHomePlc.bError THEN
            fbLog(sText := 'bDone', nFmt := cBool, bVal := PRG_AxisExample.fbHomePlc.bDone);
            fbLog(sText := 'bHomed', nFmt := cBool, bVal := PRG_AxisExample.bHomed);
            fbLog(sText := 'Axis1.Status.Homed', nFmt := cBool,
                  bVal := PRG_AxisExample.Axis1.Status.Homed);
            fbLog(sText := 'ActPos', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.ActPos);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.fbHomePlc.nErrorID);
            PRG_AxisExample.bHomeCmd := FALSE;
            nIdx := nIdx + 1;
            CASE nIdx OF
            2:
                PRG_AxisExample.stHomePlc.bMarkNcHomed := TRUE;
                nStep := 2203;
            3:
                PRG_AxisExample.fTarget := -100.0;     // onto the switch first
                PRG_AxisExample.bMoveCmd := TRUE;
                nStep := 2204;
            ELSE
                nStep := 2207;
            END_CASE
        END_IF
    2203:
        IF tonStep.ET >= T#500MS THEN
            nStep := 2201;
        END_IF
    2204:
        PRG_AxisExample.bMoveCmd := FALSE;
        fbLog(sText := 'move to -100: bAccepted', nFmt := cBool, bVal := PRG_AxisExample.bAccepted);
        nStep := 2205;
    2205:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            fbLog(sText := 'at -100: bRefSwitch', nFmt := cBool, bVal := PRG_AxisExample.bRefSwitch);
            nStep := 2206;
        END_IF
    2206:
        IF tonStep.ET >= T#500MS THEN
            nStep := 2201;
        END_IF
    2207:                                              // run 4: search timeout
        IF tonStep.ET >= T#500MS THEN
            fbLog(sText := 'run 4: switch never comes, tStepTimeout 5 s');
            PRG_AxisExample.fSwitchPos := -100000.0;
            PRG_AxisExample.stHomePlc.tStepTimeout := T#5S;
            PRG_AxisExample.bHomeCmd := TRUE;
            nStep := 2208;
        END_IF
    2208:
        IF PRG_AxisExample.fbHomePlc.bDone OR PRG_AxisExample.fbHomePlc.bError THEN
            fbLog(sText := 'bError', nFmt := cBool, bVal := PRG_AxisExample.fbHomePlc.bError);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.fbHomePlc.nErrorID);
            nStep := 2209;
        END_IF
    2209:
        IF PRG_AxisExample.Axis1.Status.NotMoving OR tonStep.ET >= T#3S THEN
            fbLog(sText := 'halted: NotMoving', nFmt := cBool,
                  bVal := PRG_AxisExample.Axis1.Status.NotMoving);
            fbLog(sText := 'SetVelo', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.SetVelo);
            PRG_AxisExample.bHomeCmd := FALSE;
            PRG_AxisExample.fSwitchPos := -50.0;
            PRG_AxisExample.stHomePlc.tStepTimeout := T#60S;
            nStep := 2210;
        END_IF
    2210:                                              // home again, so D3 can follow
        IF tonStep.ET >= T#500MS THEN
            PRG_AxisExample.bHomeCmd := TRUE;
            nStep := 2211;
        END_IF
    2211:
        tStepMax := T#300S;
        IF PRG_AxisExample.fbHomePlc.bDone OR PRG_AxisExample.fbHomePlc.bError THEN
            fbLog(sText := 're-homed for D3: bHomed', nFmt := cBool, bVal := PRG_AxisExample.bHomed);
            PRG_AxisExample.bHomeCmd := FALSE;
            bCheckDone := TRUE;
        END_IF

    // -- D3: FB_Axis moves 1 to 5 (needs a homed axis: run D2 first)
    2300:
        IF NOT PRG_AxisExample.bHomed THEN
            fbLog(sText := 'not homed: run D2 first');
            bCheckDone := TRUE;
        ELSE
            PRG_AxisExample.fTarget := 500.0;
            PRG_AxisExample.bMoveCmd := TRUE;
            nStep := 2301;
        END_IF
    2301, 2304, 2306, 2309, 2313, 2315, 2322:        // end of a command pulse
        PRG_AxisExample.bMoveCmd := FALSE;
        PRG_AxisExample.bHaltCmd := FALSE;
        PRG_AxisExample.bVeloCmd := FALSE;
        fbLog(sText := 'bAccepted', nFmt := cBool, bVal := PRG_AxisExample.bAccepted);
        nStep := nStep + 1;
    2302:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            fbLog(sText := '1 move to 500: bDone', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bDone);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.nErrorID);
            fbLog(sText := 'ActPos', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.ActPos);
            nStep := 2303;
        END_IF
    2303:
        PRG_AxisExample.fTarget := 1000.0;
        PRG_AxisExample.bMoveCmd := TRUE;
        nStep := 2304;
    2305:
        IF tonStep.ET >= T#1S THEN
            PRG_AxisExample.fTarget := 200.0;          // retarget while moving
            PRG_AxisExample.bMoveCmd := TRUE;
            nStep := 2306;
        END_IF
    2307:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            fbLog(sText := '2 retarget to 200: ActPos', nFmt := cReal,
                  fVal := PRG_AxisExample.Axis1.NcToPlc.ActPos);
            fbLog(sText := 'bCommandAborted', nFmt := cBool,
                  bVal := PRG_AxisExample.fbAxis.bCommandAborted);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.nErrorID);
            PRG_AxisExample.fTarget := 1000.0;
            PRG_AxisExample.bMoveCmd := TRUE;
            nStep := 2308;
        END_IF
    2308:
        PRG_AxisExample.bMoveCmd := FALSE;
        IF tonStep.ET >= T#1S THEN
            PRG_AxisExample.bHaltCmd := TRUE;          // halt during the move
            nStep := 2309;
        END_IF
    2310:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            fbLog(sText := '3 halt: bDone', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bDone);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.nErrorID);
            fbLog(sText := 'NotMoving', nFmt := cBool,
                  bVal := PRG_AxisExample.Axis1.Status.NotMoving);
            nStep := 2311;
        END_IF
    2311:
        PRG_AxisExample.fVeloCmd := 50.0;
        PRG_AxisExample.bVeloCmd := TRUE;
        nStep := 2312;
    2312:
        PRG_AxisExample.bVeloCmd := FALSE;
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := '4 velocity 50: SetVelo', nFmt := cReal,
                  fVal := PRG_AxisExample.Axis1.NcToPlc.SetVelo);
            PRG_AxisExample.fVeloCmd := 100.0;         // new speed while running
            PRG_AxisExample.bVeloCmd := TRUE;
            nStep := 2313;
        END_IF
    2314:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := '4 velocity 100: SetVelo', nFmt := cReal,
                  fVal := PRG_AxisExample.Axis1.NcToPlc.SetVelo);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.nErrorID);
            PRG_AxisExample.bHaltCmd := TRUE;
            nStep := 2315;
        END_IF
    2316:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            nStep := 2317;
        END_IF
    2317:
        PRG_AxisExample.fVeloCmd := 50.0;
        PRG_AxisExample.bVeloCmd := TRUE;
        nStep := 2318;
    2318:
        PRG_AxisExample.bVeloCmd := FALSE;
        IF tonStep.ET >= T#1S THEN
            PRG_AxisExample.fOverrideCmd := 50.0;      // override during a velocity move
            nStep := 2320;
        END_IF
    2320:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := '5 override 50: bBusy', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bBusy);
            fbLog(sText := 'bDone', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bDone);
            fbLog(sText := 'bCommandAborted', nFmt := cBool,
                  bVal := PRG_AxisExample.fbAxis.bCommandAborted);
            fbLog(sText := 'bError', nFmt := cBool, bVal := PRG_AxisExample.fbAxis.bError);
            fbLog(sText := 'SetVelo', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.SetVelo);
            PRG_AxisExample.fOverrideCmd := 100.0;
            nStep := 2321;
        END_IF
    2321:
        PRG_AxisExample.bHaltCmd := TRUE;
        nStep := 2322;
    2323:
        IF tonStep.ET >= T#100MS AND (PRG_AxisExample.fbAxis.bDone OR PRG_AxisExample.fbAxis.bError) THEN
            bCheckDone := TRUE;
        END_IF

    // -- D4: FB_HomeNc: timeout with the cam held FALSE, then bNoCam
    2400:
        PRG_AxisExample.cUseNcHoming := TRUE;
        PRG_AxisExample.stHomeNc.tTimeout := T#10S;
        PRG_AxisExample.stHomeNc.bNoCam := FALSE;
        PRG_AxisExample.bCamNc := FALSE;
        nStep := 2401;
    2401:
        IF tonStep.ET >= T#200MS THEN
            fbLog(sText := '1 cam held FALSE, bNoCam FALSE, timeout 10 s');
            PRG_AxisExample.bHomeCmd := TRUE;
            nStep := 2402;
        END_IF
    2402:
        IF PRG_AxisExample.fbHomeNc.bDone OR PRG_AxisExample.fbHomeNc.bError THEN
            fbLog(sText := 'bError', nFmt := cBool, bVal := PRG_AxisExample.fbHomeNc.bError);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.fbHomeNc.nErrorID);
            fbLog(sText := 'HomingState', nFmt := cDec,
                  nVal := PRG_AxisExample.Axis1.NcToPlc.HomingState);
            nStep := 2403;
        END_IF
    2403:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := '1 s later: NotMoving', nFmt := cBool,
                  bVal := PRG_AxisExample.Axis1.Status.NotMoving);
            fbLog(sText := 'SetVelo', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.SetVelo);
            PRG_AxisExample.bHomeCmd := FALSE;
            nStep := 2404;
        END_IF
    2404:
        IF bEntry THEN
            PRG_AxisExample.stHomeNc.bNoCam := TRUE;
        ELSIF tonStep.ET >= T#500MS THEN
            fbLog(sText := '2 bNoCam TRUE');
            PRG_AxisExample.bHomeCmd := TRUE;
            nStep := 2405;
        END_IF
    2405:
        IF PRG_AxisExample.fbHomeNc.bDone OR PRG_AxisExample.fbHomeNc.bError THEN
            fbLog(sText := 'bDone', nFmt := cBool, bVal := PRG_AxisExample.fbHomeNc.bDone);
            fbLog(sText := 'nErrorID', nFmt := cHex, nVal := PRG_AxisExample.fbHomeNc.nErrorID);
            fbLog(sText := 'Axis1.Status.Homed', nFmt := cBool,
                  bVal := PRG_AxisExample.Axis1.Status.Homed);
            fbLog(sText := 'ActPos', nFmt := cReal, fVal := PRG_AxisExample.Axis1.NcToPlc.ActPos);
            PRG_AxisExample.bHomeCmd := FALSE;
            bCheckDone := TRUE;                        // settle sets cUseNcHoming back
        END_IF

    ELSE
        fbLog(sText := 'no such step', nFmt := cDec, nVal := INT_TO_UDINT(nStep));
        bCheckDone := TRUE;
    END_CASE

// ---- 5. Section E: coupling, PRG_FieldTest Axis1 master, Axis2 slave
ELSIF nStep >= 3000 AND nStep < 4000 THEN
    CASE nStep OF
    // -- settle: defaults, both enabled, no error, decoupled, both standing still
    3900:
        IF bEntry THEN
            bDefaults := TRUE;
            PRG_FieldTest.bClear := TRUE;
            PRG_FieldTest.bEnable1 := TRUE;
            PRG_FieldTest.bEnable2 := TRUE;
        ELSIF tonStep.ET >= T#200MS THEN
            nStep := 3901;
        END_IF
    3901:
        PRG_FieldTest.bReset1 := PRG_FieldTest.Axis1.Status.Error;
        PRG_FieldTest.bReset2 := PRG_FieldTest.Axis2.Status.Error;
        nStep := 3902;
    3902:
        IF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bReset1 := FALSE;
            PRG_FieldTest.bReset2 := FALSE;
            IF PRG_FieldTest.Axis2.Status.Coupled THEN
                PRG_FieldTest.bGearOut := TRUE;
                PRG_FieldTest.bCamOut := TRUE;                                  // CAM
            END_IF
            nStep := 3903;
        END_IF
    3903:
        IF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bGearOut := FALSE;
            PRG_FieldTest.bCamOut := FALSE;                                     // CAM
            IF NOT PRG_FieldTest.Axis1.Status.NotMoving THEN
                PRG_FieldTest.fHaltDec1 := 500.0;
                PRG_FieldTest.bHalt1 := TRUE;
            END_IF
            IF NOT PRG_FieldTest.Axis2.Status.NotMoving THEN
                PRG_FieldTest.fHaltDec2 := 500.0;
                PRG_FieldTest.bHalt2 := TRUE;
            END_IF
            nStep := 3904;
        END_IF
    3904:
        IF tonStep.ET >= T#100MS AND PRG_FieldTest.Axis1.Status.NotMoving
           AND PRG_FieldTest.Axis2.Status.NotMoving THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.bHalt2 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            PRG_FieldTest.fHaltDec2 := 0.0;
            IF NOT (PRG_FieldTest.fbPower1.Status AND PRG_FieldTest.fbPower2.Status) THEN
                fbLog(sText := 'settle: an axis is not enabled');
            END_IF
            PRG_FieldTest.bClear := TRUE;
            nStep := nRet;
        END_IF

    // -- E1 and E7: a move and a halt on a coupled slave
    3100:
        fbLog(sText := 'fbAllowSlave2.Value', nFmt := cBool, bVal := PRG_FieldTest.fbAllowSlave2.Value);
        IF PRG_FieldTest.fbAllowSlave2.Value THEN
            nStep := 3102;
        ELSE
            fbLog(sText := 'WAIT Axis 2: allow motion cmds to slave TRUE, Download, Save now; bContinue');
            nStep := 3101;
        END_IF
    3700:
        fbLog(sText := 'fbAllowSlave2.Value', nFmt := cBool, bVal := PRG_FieldTest.fbAllowSlave2.Value);
        IF NOT PRG_FieldTest.fbAllowSlave2.Value THEN
            nStep := 3102;
        ELSE
            fbLog(sText := 'WAIT Axis 2: allow motion cmds to slave FALSE, Download, Save now; bContinue');
            nStep := 3101;
        END_IF
    3101:
        IF bEntry THEN
            bContinue := FALSE;
        END_IF
        bNoTimeout := TRUE;
        IF bContinue THEN
            bContinue := FALSE;
            fbLog(sText := 'fbAllowSlave2.Value', nFmt := cBool,
                  bVal := PRG_FieldTest.fbAllowSlave2.Value);
            nStep := 3102;
        END_IF
    3102:
        PRG_FieldTest.bGearIn := TRUE;
        nStep := 3103;
    3103:
        IF PRG_FieldTest.fbGearIn.InGear OR PRG_FieldTest.fbGearIn.Error THEN
            PRG_FieldTest.bGearIn := FALSE;
            fbLog(sText := 'GearIn at standstill: nErrGearIn', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrGearIn);
            PRG_FieldTest.bMoveVelo := TRUE;
            nStep := 3104;
        END_IF
    3104, 3110:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            nStep := nStep + 1;
        END_IF
    3105:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'coupled, master moving: Coupled', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.Coupled);
            fbLog(sText := 'ProtectedMode', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.ProtectedMode);
            PRG_FieldTest.bMoveSlave := TRUE;
            nStep := 3106;
        END_IF
    3106:
        IF PRG_FieldTest.fbMoveSlave.Done OR PRG_FieldTest.fbMoveSlave.Error
           OR PRG_FieldTest.fbMoveSlave.CommandAborted THEN
            PRG_FieldTest.bMoveSlave := FALSE;
            fbLog(sText := 'move on slave: nErrMoveSlave', nFmt := cHex,
                  nVal := PRG_FieldTest.nErrMoveSlave);
            fbLog(sText := 'Coupled', nFmt := cBool, bVal := PRG_FieldTest.Axis2.Status.Coupled);
            fbLog(sText := 'ProtectedMode', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.ProtectedMode);
            fbLog(sText := 'fbGearIn.InGear', nFmt := cBool, bVal := PRG_FieldTest.fbGearIn.InGear);
            fbLog(sText := 'fbGearIn.ErrorID', nFmt := cHex, nVal := PRG_FieldTest.fbGearIn.ErrorID);
            fbLog(sText := 'bAbortedGearIn', nFmt := cBool, bVal := PRG_FieldTest.bAbortedGearIn);
            fbLog(sText := 'slave SetPos', nFmt := cReal, fVal := PRG_FieldTest.Axis2.NcToPlc.SetPos);
            PRG_FieldTest.fHaltDec1 := 500.0;          // stop the master before coupling again
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 3107;
        END_IF
    3107:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            PRG_FieldTest.bClear := TRUE;
            nStep := 3108;
        END_IF
    3108:
        PRG_FieldTest.bGearIn := TRUE;
        nStep := 3109;
    3109:
        IF PRG_FieldTest.fbGearIn.InGear OR PRG_FieldTest.fbGearIn.Error THEN
            PRG_FieldTest.bGearIn := FALSE;
            fbLog(sText := 'GearIn again: nErrGearIn', nFmt := cHex, nVal := PRG_FieldTest.nErrGearIn);
            PRG_FieldTest.bMoveVelo := TRUE;
            nStep := 3110;
        END_IF
    3111:
        IF tonStep.ET >= T#1S THEN
            PRG_FieldTest.fHaltDec2 := 500.0;
            PRG_FieldTest.bHalt2 := TRUE;
            nStep := 3112;
        END_IF
    3112:
        IF PRG_FieldTest.fbHalt2.Done OR PRG_FieldTest.fbHalt2.Error OR tonStep.ET >= T#10S THEN
            PRG_FieldTest.bHalt2 := FALSE;
            fbLog(sText := 'halt on slave: nErrHalt2', nFmt := cHex, nVal := PRG_FieldTest.nErrHalt2);
            fbLog(sText := 'Coupled', nFmt := cBool, bVal := PRG_FieldTest.Axis2.Status.Coupled);
            fbLog(sText := 'ProtectedMode', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.ProtectedMode);
            fbLog(sText := 'fbGearIn.InGear', nFmt := cBool, bVal := PRG_FieldTest.fbGearIn.InGear);
            fbLog(sText := 'fbGearIn.ErrorID', nFmt := cHex, nVal := PRG_FieldTest.fbGearIn.ErrorID);
            fbLog(sText := 'bAbortedGearIn', nFmt := cBool, bVal := PRG_FieldTest.bAbortedGearIn);
            fbLog(sText := 'slave SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis2.NcToPlc.SetVelo);
            bCheckDone := TRUE;
        END_IF

    // -- E2: decoupling a moving slave
    3200:
        PRG_FieldTest.bGearIn := TRUE;
        nStep := 3201;
    3201:
        IF PRG_FieldTest.fbGearIn.InGear OR PRG_FieldTest.fbGearIn.Error THEN
            PRG_FieldTest.bGearIn := FALSE;
            PRG_FieldTest.bMoveVelo := TRUE;
            nStep := 3202;
        END_IF
    3202:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            nStep := 3203;
        END_IF
    3203:
        IF tonStep.ET >= T#1S THEN
            PRG_FieldTest.bGearOut := TRUE;
            nStep := 3204;
        END_IF
    3204:
        IF PRG_FieldTest.fbGearOut.Done OR PRG_FieldTest.fbGearOut.Error THEN
            PRG_FieldTest.bGearOut := FALSE;
            fbLog(sText := 'nErrGearOut', nFmt := cHex, nVal := PRG_FieldTest.nErrGearOut);
            nStep := 3205;
        END_IF
    3205:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'decoupled: slave SetVelo', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetVelo);
            fbLog(sText := 'ContinuousMotion', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.ContinuousMotion);
            fbLog(sText := 'Coupled', nFmt := cBool, bVal := PRG_FieldTest.Axis2.Status.Coupled);
            PRG_FieldTest.fHaltDec1 := 500.0;
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 3206;
        END_IF
    3206:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            nStep := 3207;
        END_IF
    3207:
        IF tonStep.ET >= T#2S THEN
            fbLog(sText := 'master stopped: slave SetVelo', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetVelo);
            fbLog(sText := 'ContinuousMotion', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.ContinuousMotion);
            bCheckDone := TRUE;
        END_IF

    // -- E3: MC_Halt 0 on a decoupled slave, master fDec 500 then 200
    3300:
        nIdx := 1;
        fbLog(sText := 'record Axis 2 default deceleration and jerk from XAE');
        nStep := 3301;
    3301:
        PRG_FieldTest.fVelo := 500.0;                  // as C3: keeps jerk from hiding the result
        PRG_FieldTest.fDec := aE3Dec[nIdx];
        PRG_FieldTest.bGearIn := TRUE;
        nStep := 3302;
    3302:
        IF PRG_FieldTest.fbGearIn.InGear OR PRG_FieldTest.fbGearIn.Error THEN
            PRG_FieldTest.bGearIn := FALSE;
            PRG_FieldTest.bMoveVelo := TRUE;
            nStep := 3303;
        END_IF
    3303:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            PRG_FieldTest.bGearOut := TRUE;
            nStep := 3304;
        END_IF
    3304:
        IF PRG_FieldTest.fbGearOut.Done OR PRG_FieldTest.fbGearOut.Error THEN
            PRG_FieldTest.bGearOut := FALSE;
            PRG_FieldTest.fHaltDec2 := 0.0;
            PRG_FieldTest.bHalt2 := TRUE;
            nStep := 3305;
        END_IF
    3305:
        IF PRG_FieldTest.fbHalt2.Done OR PRG_FieldTest.fbHalt2.Error THEN
            PRG_FieldTest.bHalt2 := FALSE;
            fbLog(sText := 'master fDec', nFmt := cReal, fVal := aE3Dec[nIdx]);
            fbLog(sText := 'slave fPeakDecel2', nFmt := cReal, fVal := PRG_FieldTest.fPeakDecel2);
            fbLog(sText := 'nErrHalt2', nFmt := cHex, nVal := PRG_FieldTest.nErrHalt2);
            PRG_FieldTest.fHaltDec1 := 500.0;
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 3306;
        END_IF
    3306:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            nIdx := nIdx + 1;
            IF nIdx <= 2 THEN
                nStep := 3301;
            ELSE
                bCheckDone := TRUE;
            END_IF
        END_IF

    // -- E4: MC_GearInDyn with Enable FALSE, then MC_GearOut while Enable is TRUE
    3400:
        PRG_FieldTest.bMoveVelo := TRUE;
        nStep := 3401;
    3401:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            PRG_FieldTest.bGearInDyn := TRUE;
            nStep := 3402;
        END_IF
    3402:
        IF PRG_FieldTest.fbGearInDyn.InGear OR PRG_FieldTest.fbGearInDyn.Error THEN
            fbLog(sText := 'GearInDyn: InGear', nFmt := cBool, bVal := PRG_FieldTest.fbGearInDyn.InGear);
            fbLog(sText := 'nErrGearInDyn', nFmt := cHex, nVal := PRG_FieldTest.nErrGearInDyn);
            PRG_FieldTest.bGearInDyn := FALSE;
            nStep := 3403;
        END_IF
    3403:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'Enable FALSE: Coupled', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.Coupled);
            fbLog(sText := 'slave SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis2.NcToPlc.SetVelo);
            fbLog(sText := 'master SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis1.NcToPlc.SetVelo);
            PRG_FieldTest.bGearInDyn := TRUE;
            nStep := 3404;
        END_IF
    3404:
        IF PRG_FieldTest.fbGearInDyn.InGear OR PRG_FieldTest.fbGearInDyn.Error THEN
            PRG_FieldTest.bGearOut := TRUE;            // Enable stays TRUE
            nStep := 3405;
        END_IF
    3405:
        IF PRG_FieldTest.fbGearOut.Done OR PRG_FieldTest.fbGearOut.Error OR tonStep.ET >= T#1S THEN
            PRG_FieldTest.bGearOut := FALSE;
            nStep := 3406;
        END_IF
    3406:
        IF tonStep.ET >= T#1S THEN                     // the mask lines show the second
            fbLog(sText := 'GearOut, Enable TRUE: Coupled', nFmt := cBool,
                  bVal := PRG_FieldTest.Axis2.Status.Coupled);
            fbLog(sText := 'fbGearInDyn.InGear', nFmt := cBool,
                  bVal := PRG_FieldTest.fbGearInDyn.InGear);
            fbLog(sText := 'nErrGearInDyn', nFmt := cHex, nVal := PRG_FieldTest.nErrGearInDyn);
            fbLog(sText := 'nErrGearOut', nFmt := cHex, nVal := PRG_FieldTest.nErrGearOut);
            fbLog(sText := 'slave SetVelo', nFmt := cReal, fVal := PRG_FieldTest.Axis2.NcToPlc.SetVelo);
            PRG_FieldTest.bGearInDyn := FALSE;
            bCheckDone := TRUE;
        END_IF

    // -- E5: MC_CamIn with the slave away from its table position (TF5050)
    3500:                                                                       // CAM
        PRG_FieldTest.fPosA := 100.0;                                           // CAM
        PRG_FieldTest.fPosSlave := 0.0;                                         // CAM
        PRG_FieldTest.bMoveA := TRUE;                                           // CAM
        PRG_FieldTest.bMoveSlave := TRUE;                                       // CAM
        nStep := 3501;                                                          // CAM
    3501:                                                                       // CAM
        tStepMax := T#120S;                            // repositioning, long after E3 // CAM
        IF (PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error)          // CAM
           AND (PRG_FieldTest.fbMoveSlave.Done OR PRG_FieldTest.fbMoveSlave.Error) THEN // CAM
            PRG_FieldTest.bMoveA := FALSE;                                      // CAM
            PRG_FieldTest.bMoveSlave := FALSE;                                  // CAM
            PRG_FieldTest.bCamSelect := TRUE;                                   // CAM
            nStep := 3502;                                                      // CAM
        END_IF                                                                  // CAM
    3502:                                                                       // CAM
        IF PRG_FieldTest.fbCamSelect.Done OR PRG_FieldTest.fbCamSelect.Error THEN // CAM
            PRG_FieldTest.bCamSelect := FALSE;                                  // CAM
            fbLog(sText := 'nErrCamSelect', nFmt := cHex,                       // CAM
                  nVal := PRG_FieldTest.nErrCamSelect);                         // CAM
            fbLog(sText := '1 before CamIn: slave SetPos', nFmt := cReal,       // CAM
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetPos);                  // CAM
            PRG_FieldTest.bCamIn := TRUE;                                       // CAM
            nStep := 3503;                                                      // CAM
        END_IF                                                                  // CAM
    3503, 3507:                                                                 // CAM
        IF tonStep.ET >= T#1S THEN                                              // CAM
            PRG_FieldTest.bCamIn := FALSE;                                      // CAM
            fbLog(sText := 'CamIn, master standing: slave SetPos', nFmt := cReal, // CAM
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetPos);                  // CAM
            fbLog(sText := 'InSync', nFmt := cBool,                             // CAM
                  bVal := PRG_FieldTest.fbCamIn.InSync);                        // CAM
            fbLog(sText := 'nErrCamIn', nFmt := cHex,                           // CAM
                  nVal := PRG_FieldTest.nErrCamIn);                             // CAM
            fbLog(sText := 'nAxisErr2', nFmt := cHex,                           // CAM
                  nVal := PRG_FieldTest.nAxisErr2);                             // CAM
            IF nStep = 3503 THEN                                                // CAM
                PRG_FieldTest.fPosA := 150.0;                                   // CAM
            ELSE                                                                // CAM
                PRG_FieldTest.fPosA := 120.0;                                   // CAM
            END_IF                                                              // CAM
            PRG_FieldTest.bMoveA := TRUE;                                       // CAM
            nStep := nStep + 1;                                                 // CAM
        END_IF                                                                  // CAM
    3504, 3508:                                                                 // CAM
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error THEN       // CAM
            PRG_FieldTest.bMoveA := FALSE;                                      // CAM
            fbLog(sText := 'master moved to', nFmt := cReal,                    // CAM
                  fVal := PRG_FieldTest.Axis1.NcToPlc.SetPos);                  // CAM
            fbLog(sText := 'slave SetPos', nFmt := cReal,                       // CAM
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetPos);                  // CAM
            fbLog(sText := 'nErrCamIn', nFmt := cHex,                           // CAM
                  nVal := PRG_FieldTest.nErrCamIn);                             // CAM
            fbLog(sText := 'nAxisErr2', nFmt := cHex,                           // CAM
                  nVal := PRG_FieldTest.nAxisErr2);                             // CAM
            IF nStep = 3504 THEN                                                // CAM
                PRG_FieldTest.bCamOut := TRUE;                                  // CAM
                nStep := 3505;                                                  // CAM
            ELSE                                                                // CAM
                bCheckDone := TRUE;                                             // CAM
            END_IF                                                              // CAM
        END_IF                                                                  // CAM
    3505:                                                                       // CAM
        IF PRG_FieldTest.fbCamOut.Done OR PRG_FieldTest.fbCamOut.Error THEN     // CAM
            PRG_FieldTest.bCamOut := FALSE;                                     // CAM
            PRG_FieldTest.fPosA := 100.0;                                       // CAM
            PRG_FieldTest.bMoveA := TRUE;                                       // CAM
            nStep := 3506;                                                      // CAM
        END_IF                                                                  // CAM
    3506:                                                                       // CAM
        IF PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error THEN       // CAM
            PRG_FieldTest.bMoveA := FALSE;                                      // CAM
            fbLog(sText := '2 master offset 20, scaling 2, slave offset 5');    // CAM
            PRG_FieldTest.fMasterOffset := 20.0;                                // CAM
            PRG_FieldTest.fMasterScaling := 2.0;                                // CAM
            PRG_FieldTest.fSlaveOffset := 5.0;                                  // CAM
            PRG_FieldTest.bClear := TRUE;                                       // CAM
            PRG_FieldTest.bCamIn := TRUE;                                       // CAM
            nStep := 3507;                                                      // CAM
        END_IF                                                                  // CAM

    // -- E6: phasing on an MC_CamIn, an MC_GearIn and an MC_GearInDyn slave
    3600:
        nIdx := 2;                                     // without camming: MC_GearIn first
        nIdx := 1;                                                              // CAM
        nStep := 3601;
    3601:                                              // both axes to 0, at standstill
        PRG_FieldTest.fVelo := 100.0;
        PRG_FieldTest.fPosA := 0.0;
        PRG_FieldTest.fPosSlave := 0.0;
        PRG_FieldTest.bMoveA := TRUE;
        PRG_FieldTest.bMoveSlave := TRUE;
        IF nIdx = 1 THEN
            PRG_FieldTest.bCamSelect := TRUE;                                   // CAM
        END_IF
        nStep := 3602;
    3602:                                              // 500 ms: the cam table is selected
        tStepMax := T#120S;                            // repositioning, long after E3
        IF tonStep.ET >= T#500MS
           AND (PRG_FieldTest.fbMoveA.Done OR PRG_FieldTest.fbMoveA.Error)
           AND (PRG_FieldTest.fbMoveSlave.Done OR PRG_FieldTest.fbMoveSlave.Error) THEN
            PRG_FieldTest.bMoveA := FALSE;
            PRG_FieldTest.bMoveSlave := FALSE;
            PRG_FieldTest.bCamSelect := FALSE;                                  // CAM
            CASE nIdx OF
            1:
                fbLog(sText := 'phasing on MC_CamIn');
                PRG_FieldTest.bCamIn := TRUE;                                   // CAM
            2:
                fbLog(sText := 'phasing on MC_GearIn');
                PRG_FieldTest.bGearIn := TRUE;
            3:
                fbLog(sText := 'phasing on MC_GearInDyn');
                PRG_FieldTest.bGearInDyn := TRUE;      // Enable, stays TRUE
            END_CASE
            nStep := 3603;
        END_IF
    3603:
        IF tonStep.ET >= T#1S THEN
            PRG_FieldTest.bCamIn := FALSE;                                      // CAM
            PRG_FieldTest.bGearIn := FALSE;
            fbLog(sText := 'Coupled', nFmt := cBool, bVal := PRG_FieldTest.Axis2.Status.Coupled);
            PRG_FieldTest.fVelo := 30.0;               // master and phasing velocity
            PRG_FieldTest.bMoveVelo := TRUE;
            nStep := 3604;
        END_IF
    3604:
        IF PRG_FieldTest.fbMoveVelo.InVelocity OR PRG_FieldTest.fbMoveVelo.Error THEN
            PRG_FieldTest.bMoveVelo := FALSE;
            nStep := 3605;
        END_IF
    3605:
        IF tonStep.ET >= T#1S THEN
            fDiff0 := PRG_FieldTest.Axis2.NcToPlc.SetPos - PRG_FieldTest.Axis1.NcToPlc.SetPos;
            PRG_FieldTest.bClear := TRUE;
            PRG_FieldTest.bPhasing := TRUE;
            nStep := 3606;
        END_IF
    3606:
        IF PRG_FieldTest.fbPhasing.Done OR PRG_FieldTest.fbPhasing.Error OR tonStep.ET >= T#10S THEN
            PRG_FieldTest.bPhasing := FALSE;
            nStep := 3607;
        END_IF
    3607:
        IF tonStep.ET >= T#1S THEN
            fbLog(sText := 'nErrPhasing', nFmt := cHex, nVal := PRG_FieldTest.nErrPhasing);
            fbLog(sText := 'shift (change of slave - master)', nFmt := cReal,
                  fVal := PRG_FieldTest.Axis2.NcToPlc.SetPos - PRG_FieldTest.Axis1.NcToPlc.SetPos
                          - fDiff0);
            PRG_FieldTest.fHaltDec1 := 500.0;
            PRG_FieldTest.bHalt1 := TRUE;
            nStep := 3608;
        END_IF
    3608:
        IF PRG_FieldTest.fbHalt1.Done OR PRG_FieldTest.fbHalt1.Error THEN
            PRG_FieldTest.bHalt1 := FALSE;
            PRG_FieldTest.fHaltDec1 := 0.0;
            PRG_FieldTest.bGearInDyn := FALSE;
            PRG_FieldTest.bGearOut := TRUE;
            PRG_FieldTest.bCamOut := TRUE;                                      // CAM
            nStep := 3609;
        END_IF
    3609:
        IF tonStep.ET >= T#500MS THEN
            PRG_FieldTest.bGearOut := FALSE;
            PRG_FieldTest.bCamOut := FALSE;                                     // CAM
            nIdx := nIdx + 1;
            IF nIdx <= 3 THEN
                nStep := 3601;
            ELSE
                bCheckDone := TRUE;
            END_IF
        END_IF

    ELSE
        fbLog(sText := 'no such step (CAM lines deleted?)', nFmt := cDec,
              nVal := INT_TO_UDINT(nStep));
        bCheckDone := TRUE;
    END_CASE
END_IF

// ---- 6. End of a check: next check, or settle and stop
IF bCheckDone THEN
    bCheckDone := FALSE;
    bRelease := TRUE;
    fbLog(sText := 'END');
    IF bRunAll AND nCheck < aLastCheck[nSection] THEN
        nCheck := nCheck + 1;
        fbLog.sTag := CONCAT(aSecName[nSection], INT_TO_STRING(nCheck));
        fbLog(sText := 'START');
        nRet := 1000 * nSection + 100 * nCheck;
    ELSE
        bRunAll := FALSE;
        nRet := 0;
    END_IF
    nStep := 1000 * nSection + 900;
END_IF
IF nStep = 0 AND nStepLast <> 0 AND NOT tonStep.Q THEN
    fbLog(sText := 'IDLE');
END_IF

// ---- 7. Release commands, restore defaults
IF bRelease THEN
    bRelease := FALSE;
    PRG_FieldTest.bReset1 := FALSE;
    PRG_FieldTest.bReset2 := FALSE;
    PRG_FieldTest.bMoveA := FALSE;
    PRG_FieldTest.bMoveB := FALSE;
    PRG_FieldTest.bMoveVelo := FALSE;
    PRG_FieldTest.bHalt1 := FALSE;
    PRG_FieldTest.bStop1 := FALSE;
    PRG_FieldTest.bSetPos1 := FALSE;
    PRG_FieldTest.bHome1 := FALSE;
    PRG_FieldTest.bGearIn := FALSE;
    PRG_FieldTest.bGearOut := FALSE;
    PRG_FieldTest.bGearInDyn := FALSE;
    PRG_FieldTest.bMoveSlave := FALSE;
    PRG_FieldTest.bHalt2 := FALSE;
    PRG_FieldTest.bPhasing := FALSE;
    PRG_FieldTest.bCamSelect := FALSE;                                          // CAM
    PRG_FieldTest.bCamIn := FALSE;                                              // CAM
    PRG_FieldTest.bCamOut := FALSE;                                             // CAM
    PRG_AxisExample.bHomeCmd := FALSE;
    PRG_AxisExample.bMoveCmd := FALSE;
    PRG_AxisExample.bHaltCmd := FALSE;
    PRG_AxisExample.bResetCmd := FALSE;
    PRG_AxisExample.bVeloCmd := FALSE;
END_IF

IF bDefaults THEN
    bDefaults := FALSE;
    PRG_FieldTest.bEnPos1 := TRUE;
    PRG_FieldTest.bEnNeg1 := TRUE;
    PRG_FieldTest.bEnPos2 := TRUE;
    PRG_FieldTest.bEnNeg2 := TRUE;
    PRG_FieldTest.fOverride1 := 100.0;
    PRG_FieldTest.fVelo := 100.0;
    PRG_FieldTest.fAcc := 500.0;
    PRG_FieldTest.fDec := 500.0;
    PRG_FieldTest.fPosA := 1000.0;
    PRG_FieldTest.fPosB := 400.0;
    PRG_FieldTest.fHaltDec1 := 0.0;
    PRG_FieldTest.fStopDec1 := 500.0;
    PRG_FieldTest.fSetPos1 := 0.0;
    PRG_FieldTest.bSetPosRelative1 := FALSE;
    PRG_FieldTest.eHomeMode1 := MC_HomingMode.MC_Direct;
    PRG_FieldTest.fHomePos1 := 0.0;
    PRG_FieldTest.bCam1 := FALSE;
    PRG_FieldTest.fRatio := 1.0;
    PRG_FieldTest.fPosSlave := 100.0;
    PRG_FieldTest.fHaltDec2 := 0.0;
    PRG_FieldTest.fPhaseShift := 10.0;
    PRG_FieldTest.fMasterOffset := 0.0;                                         // CAM
    PRG_FieldTest.fSlaveOffset := 0.0;                                          // CAM
    PRG_FieldTest.fMasterScaling := 1.0;                                        // CAM
    PRG_FieldTest.fSlaveScaling := 1.0;                                         // CAM
    PRG_AxisExample.stHomePlc.bMarkNcHomed := FALSE;
    PRG_AxisExample.stHomePlc.tStepTimeout := T#60S;
    PRG_AxisExample.fSwitchPos := -50.0;
    PRG_AxisExample.cUseNcHoming := FALSE;
    PRG_AxisExample.bCamNc := FALSE;
    PRG_AxisExample.stHomeNc.bNoCam := FALSE;
    PRG_AxisExample.stHomeNc.tTimeout := T#60S;
    PRG_AxisExample.fVeloCmd := 50.0;
    PRG_AxisExample.fOverrideCmd := 100.0;
END_IF

// ---- 8. Step timeout
IF nStep <> nStepLast THEN
    tonStep(IN := FALSE);                              // the step changed this cycle
ELSE
    tonStep(IN := nStep <> 0 AND NOT bNoTimeout, PT := tStepMax);
END_IF
IF tonStep.Q THEN
    fbLog(sText := 'TIMEOUT in step', nFmt := cDec, nVal := INT_TO_UDINT(nStep));
    bRunAll := FALSE;
    bRelease := TRUE;                                  // done next cycle, in part 7
    IF (nStep MOD 1000) < 900 THEN
        nRet := 0;
        nStep := 1000 * nSection + 900;               // settle: halts the axes, then idle
    ELSE
        nStep := 0;                                    // the settle chain itself timed out
    END_IF
END_IF

// ---- 9. FB-flag mask and HomingState, logged when they change
IF nStep <> 0 THEN
    dwMask := 0;
    IF nSection = 1 THEN
        dwMask.0 := PRG_FieldTest.fbPower1.Status;
        dwMask.1 := PRG_FieldTest.Axis1.Status.Error;
        dwMask.2 := PRG_FieldTest.Axis1.Status.ErrorStop;
        dwMask.3 := PRG_FieldTest.Axis1.Status.Homed;
        dwMask.4 := PRG_FieldTest.Axis1.Status.MotionCommandsLocked;
        dwMask.5 := PRG_FieldTest.Axis1.Status.NotMoving;
        dwMask.6 := PRG_FieldTest.fbMoveA.Busy;
        dwMask.7 := PRG_FieldTest.fbMoveA.Done;
        dwMask.8 := PRG_FieldTest.fbMoveA.Error;
        dwMask.9 := PRG_FieldTest.fbMoveA.CommandAborted;
        dwMask.10 := PRG_FieldTest.fbMoveB.Busy;
        dwMask.11 := PRG_FieldTest.fbMoveB.Done;
        dwMask.12 := PRG_FieldTest.fbMoveB.Error;
        dwMask.13 := PRG_FieldTest.fbMoveB.CommandAborted;
        dwMask.14 := PRG_FieldTest.fbMoveVelo.Busy;
        dwMask.15 := PRG_FieldTest.fbMoveVelo.InVelocity;
        dwMask.16 := PRG_FieldTest.fbMoveVelo.Error;
        dwMask.17 := PRG_FieldTest.fbMoveVelo.CommandAborted;
        dwMask.18 := PRG_FieldTest.fbHalt1.Busy;
        dwMask.19 := PRG_FieldTest.fbHalt1.Done;
        dwMask.20 := PRG_FieldTest.fbHalt1.Error;
        dwMask.21 := PRG_FieldTest.fbStop1.Busy;
        dwMask.22 := PRG_FieldTest.fbStop1.Done;
        dwMask.23 := PRG_FieldTest.fbStop1.Error;
        dwMask.24 := PRG_FieldTest.fbHome1.Busy;
        dwMask.25 := PRG_FieldTest.fbHome1.Done;
        dwMask.26 := PRG_FieldTest.fbHome1.Error;
        dwMask.27 := PRG_FieldTest.fbHome1.CommandAborted;
        dwMask.28 := PRG_FieldTest.fbSetPos1.Done;
        dwMask.29 := PRG_FieldTest.fbSetPos1.Error;
        dwMask.30 := PRG_FieldTest.fbReset1.Done;
        dwMask.31 := PRG_FieldTest.fbReset1.Error;
        nHs := PRG_FieldTest.Axis1.NcToPlc.HomingState;
    ELSIF nSection = 2 THEN
        dwMask.0 := PRG_AxisExample.fbAxis.bReady;
        dwMask.1 := PRG_AxisExample.fbAxis.bBusy;
        dwMask.2 := PRG_AxisExample.fbAxis.bDone;
        dwMask.3 := PRG_AxisExample.fbAxis.bCommandAborted;
        dwMask.4 := PRG_AxisExample.fbAxis.bError;
        dwMask.5 := PRG_AxisExample.bAccepted;
        dwMask.6 := PRG_AxisExample.fbHomePlc.bBusy;
        dwMask.7 := PRG_AxisExample.fbHomePlc.bDone;
        dwMask.8 := PRG_AxisExample.fbHomePlc.bError;
        dwMask.9 := PRG_AxisExample.fbHomePlc.bHomed;
        dwMask.10 := PRG_AxisExample.fbHomeNc.bBusy;
        dwMask.11 := PRG_AxisExample.fbHomeNc.bDone;
        dwMask.12 := PRG_AxisExample.fbHomeNc.bError;
        dwMask.13 := PRG_AxisExample.bHomed;
        dwMask.14 := PRG_AxisExample.bError;
        dwMask.15 := PRG_AxisExample.Axis1.Status.Homed;
        dwMask.16 := PRG_AxisExample.Axis1.Status.Error;
        dwMask.17 := PRG_AxisExample.Axis1.Status.NotMoving;
        dwMask.18 := PRG_AxisExample.bRefSwitch;
        dwMask.19 := PRG_AxisExample.bCamNc;
        dwMask.20 := PRG_AxisExample.Axis1.Status.HomingBusy;
        nHs := PRG_AxisExample.Axis1.NcToPlc.HomingState;
    ELSE
        dwMask.0 := PRG_FieldTest.fbPower1.Status;
        dwMask.1 := PRG_FieldTest.fbPower2.Status;
        dwMask.2 := PRG_FieldTest.Axis1.Status.Error;
        dwMask.3 := PRG_FieldTest.Axis2.Status.Error;
        dwMask.4 := PRG_FieldTest.Axis2.Status.Coupled;
        dwMask.5 := PRG_FieldTest.Axis2.Status.ProtectedMode;
        dwMask.6 := PRG_FieldTest.Axis2.Status.NotMoving;
        dwMask.7 := PRG_FieldTest.Axis2.Status.ContinuousMotion;
        dwMask.8 := PRG_FieldTest.fbGearIn.Busy;
        dwMask.9 := PRG_FieldTest.fbGearIn.InGear;
        dwMask.10 := PRG_FieldTest.fbGearIn.Error;
        dwMask.11 := PRG_FieldTest.fbGearIn.CommandAborted;
        dwMask.12 := PRG_FieldTest.fbGearOut.Done;
        dwMask.13 := PRG_FieldTest.fbGearOut.Error;
        dwMask.14 := PRG_FieldTest.fbGearInDyn.InGear;
        dwMask.15 := PRG_FieldTest.fbGearInDyn.Error;
        dwMask.16 := PRG_FieldTest.fbMoveSlave.Busy;
        dwMask.17 := PRG_FieldTest.fbMoveSlave.Done;
        dwMask.18 := PRG_FieldTest.fbMoveSlave.Error;
        dwMask.19 := PRG_FieldTest.fbMoveSlave.CommandAborted;
        dwMask.20 := PRG_FieldTest.fbHalt2.Busy;
        dwMask.21 := PRG_FieldTest.fbHalt2.Done;
        dwMask.22 := PRG_FieldTest.fbHalt2.Error;
        dwMask.23 := PRG_FieldTest.fbPhasing.Busy;
        dwMask.24 := PRG_FieldTest.fbPhasing.Done;
        dwMask.25 := PRG_FieldTest.fbPhasing.Error;
        dwMask.26 := PRG_FieldTest.fbCamSelect.Done;                            // CAM
        dwMask.27 := PRG_FieldTest.fbCamSelect.Error;                           // CAM
        dwMask.28 := PRG_FieldTest.fbCamIn.InSync;                              // CAM
        dwMask.29 := PRG_FieldTest.fbCamIn.Error;                               // CAM
        dwMask.30 := PRG_FieldTest.fbCamOut.Done;                               // CAM
        dwMask.31 := PRG_FieldTest.fbMoveVelo.InVelocity;
        nHs := nHsPrev;                                // no homing in section E
    END_IF
    IF bMaskFirst OR dwMask <> dwMaskPrev THEN
        IF bMaskFirst THEN
            dwMaskPrev := NOT dwMask;                  // every bit shows as changed
        END_IF
        fbLog(sText := 'M', nFmt := cMask, nVal := DWORD_TO_UDINT(dwMask),
              nVal2 := DWORD_TO_UDINT(dwMask XOR dwMaskPrev));
        dwMaskPrev := dwMask;
        bMaskFirst := FALSE;
    END_IF
    IF nHs <> nHsPrev THEN
        fbLog(sText := 'HomingState', nFmt := cDec, nVal := nHs);
        nHsPrev := nHs;
    END_IF
END_IF

fbLog();                                               // keeps the clock running
// ==== PRG_FieldTestSeq END IMPLEMENTATION ====
