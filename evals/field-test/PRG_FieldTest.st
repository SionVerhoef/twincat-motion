// PRG_FieldTest: test program for the twincat-motion field test (evals/field-test/README.md).
//
// Use it in a THROWAWAY TwinCAT project with simulated NC axes only.
// 1. Add a PROGRAM named PRG_FieldTest (Structured Text) and call it from MAIN or the task.
// 2. Paste the DECLARATION part into the declaration pane, the IMPLEMENTATION part into
//    the code pane.
// 3. Libraries: Tc2_MC2. Sections E5 and E6 also need Tc2_MC2_Camming (TF5050; a 7-day
//    trial licence is enough). Without it, delete every line that ends in // CAM.
// 4. Link Axis1 and Axis2 to two simulated NC axes (NC axis > Settings > Link To PLC).
// 5. Drive it from the online view: write TRUE to a b... command, read the results.
//    Every Execute is a plain BOOL: write FALSE again before the next TRUE, or there is
//    no rising edge. Results latch until you write bClear := TRUE.
//
// Built on TwinCAT 4024.55 with Tc2_MC2 3.3.59 and Tc2_MC2_Camming 3.4.0. On other
// versions, fix compile errors on site and note them in the results.

// ==== DECLARATION ====
PROGRAM PRG_FieldTest
VAR
    Axis1            : AXIS_REF;   // simulated axis; master in section E
    Axis2            : AXIS_REF;   // simulated axis; slave in section E

    // --- power and reset
    bEnable1         : BOOL;
    bEnPos1          : BOOL := TRUE;
    bEnNeg1          : BOOL := TRUE;
    fOverride1       : LREAL := 100.0;
    bEnable2         : BOOL;
    bEnPos2          : BOOL := TRUE;
    bEnNeg2          : BOOL := TRUE;
    bReset1          : BOOL;
    bReset2          : BOOL;
    fbPower1         : MC_Power;
    fbPower2         : MC_Power;
    fbReset1         : MC_Reset;
    fbReset2         : MC_Reset;

    // --- moves and stops on Axis1 (units of the axis, e.g. mm, mm/s, mm/s^2)
    fVelo            : LREAL := 100.0;
    fAcc             : LREAL := 500.0;
    fDec             : LREAL := 500.0;
    bMoveA           : BOOL;
    fPosA            : LREAL := 1000.0;
    fbMoveA          : MC_MoveAbsolute;
    bMoveB           : BOOL;
    fPosB            : LREAL := 400.0;
    fbMoveB          : MC_MoveAbsolute;
    bMoveVelo        : BOOL;
    fbMoveVelo       : MC_MoveVelocity;
    bHalt1           : BOOL;
    fHaltDec1        : LREAL;            // 0 on purpose: test C3
    fbHalt1          : MC_Halt;
    bStop1           : BOOL;
    fStopDec1        : LREAL := 500.0;
    fbStop1          : MC_Stop;
    bSetPos1         : BOOL;
    fSetPos1         : LREAL;
    bSetPosRelative1 : BOOL;             // MC_SetPosition.Mode: TRUE relative
    fbSetPos1        : MC_SetPosition;
    bHome1           : BOOL;
    eHomeMode1       : MC_HomingMode := MC_HomingMode.MC_Direct;
    fHomePos1        : LREAL;
    bCam1            : BOOL;             // bCalibrationCam for MC_DefaultHoming
    fbHome1          : MC_Home;

    // --- coupling: Axis1 master, Axis2 slave
    fRatio           : LREAL := 1.0;
    bGearIn          : BOOL;
    fbGearIn         : MC_GearIn;
    bGearOut         : BOOL;
    fbGearOut        : MC_GearOut;
    bGearInDyn       : BOOL;             // this one is Enable: a level, not an edge
    fbGearInDyn      : MC_GearInDyn;
    bMoveSlave       : BOOL;
    fPosSlave        : LREAL := 100.0;
    fbMoveSlave      : MC_MoveAbsolute;
    bHalt2           : BOOL;
    fHaltDec2        : LREAL;            // 0 on purpose: test E3
    fbHalt2          : MC_Halt;
    bPhasing         : BOOL;
    fPhaseShift      : LREAL := 10.0;
    fbPhasing        : MC_PhasingRelative;
    aCamTable        : ARRAY[0..36, 0..1] OF LREAL;  // CAM straight line, slave = master, 0..360
    stCamRef         : MC_CAM_REF;                   // CAM
    bCamTableReady   : BOOL;                         // CAM
    bCamSelect       : BOOL;                         // CAM
    fbCamSelect      : MC_CamTableSelect;            // CAM
    bCamIn           : BOOL;                         // CAM
    fMasterOffset    : LREAL;                        // CAM
    fSlaveOffset     : LREAL;                        // CAM
    fMasterScaling   : LREAL := 1.0;                 // CAM
    fSlaveScaling    : LREAL := 1.0;                 // CAM
    fbCamIn          : MC_CamIn;                     // CAM
    bCamOut          : BOOL;                         // CAM
    fbCamOut         : MC_CamOut;                    // CAM

    // --- axis parameters as the running NC has them (test A3)
    fbAllowSlave1    : MC_ReadBoolParameter;
    fbAllowSlave2    : MC_ReadBoolParameter;
    fbLagMon1        : MC_ReadBoolParameter;
    fbLagMon2        : MC_ReadBoolParameter;
    fbAllowExt1      : MC_ReadBoolParameter;

    // --- results: first error per block and per axis, latched until bClear
    bClear           : BOOL;
    nErrPower1       : UDINT;
    nErrPower2       : UDINT;
    nErrReset1       : UDINT;
    nErrMoveA        : UDINT;
    nErrMoveB        : UDINT;
    nErrMoveVelo     : UDINT;
    nErrHalt1        : UDINT;
    nErrStop1        : UDINT;
    nErrSetPos1      : UDINT;
    nErrHome1        : UDINT;
    nErrGearIn       : UDINT;
    nErrGearOut      : UDINT;
    nErrGearInDyn    : UDINT;
    nErrMoveSlave    : UDINT;
    nErrHalt2        : UDINT;
    nErrPhasing      : UDINT;
    nErrCamSelect    : UDINT;                        // CAM
    nErrCamIn        : UDINT;                        // CAM
    nAxisErr1        : UDINT;            // first axis error seen on Axis1
    nAxisErr2        : UDINT;
    bAbortedA        : BOOL;             // CommandAborted seen
    bAbortedB        : BOOL;
    bAbortedVelo     : BOOL;
    bAbortedGearIn   : BOOL;
    bAbortedHome1    : BOOL;
    bStatusDropped1  : BOOL;             // MC_Power.Status fell while Enable stayed TRUE
    fPeakDecel1      : LREAL;            // largest |SetAcc| while fbHalt1 was busy
    fPeakDecel2      : LREAL;            // the same for fbHalt2
    nStopRelease     : UDINT;            // PLC cycles from bStop1 FALSE until fbStop1.Busy FALSE
    bStopCounting    : BOOL;
    bStatusPrev1     : BOOL;
    rtHalt1          : R_TRIG;
    rtHalt2          : R_TRIG;
    ftStop1          : F_TRIG;
    i                : INT;
END_VAR
// ==== END DECLARATION ====

// ==== IMPLEMENTATION ====
// Fresh status every cycle, before anything reads it.
Axis1.ReadStatus();
Axis2.ReadStatus();

IF bClear THEN
    bClear := FALSE;
    nErrPower1 := 0;  nErrPower2 := 0;  nErrReset1 := 0;
    nErrMoveA := 0;   nErrMoveB := 0;   nErrMoveVelo := 0;
    nErrHalt1 := 0;   nErrStop1 := 0;   nErrSetPos1 := 0;  nErrHome1 := 0;
    nErrGearIn := 0;  nErrGearOut := 0; nErrGearInDyn := 0;
    nErrMoveSlave := 0; nErrHalt2 := 0; nErrPhasing := 0;
    nErrCamSelect := 0;                                         // CAM
    nErrCamIn := 0;                                             // CAM
    nAxisErr1 := 0;   nAxisErr2 := 0;
    bAbortedA := FALSE; bAbortedB := FALSE; bAbortedVelo := FALSE;
    bAbortedGearIn := FALSE; bAbortedHome1 := FALSE;
    bStatusDropped1 := FALSE;
    fPeakDecel1 := 0; fPeakDecel2 := 0; nStopRelease := 0;
END_IF

// Power and reset: called every cycle, unconditionally.
fbPower1(Axis := Axis1, Enable := bEnable1, Enable_Positive := bEnPos1,
         Enable_Negative := bEnNeg1, Override := fOverride1);
fbPower2(Axis := Axis2, Enable := bEnable2, Enable_Positive := bEnPos2,
         Enable_Negative := bEnNeg2, Override := 100.0);
fbReset1(Axis := Axis1, Execute := bReset1);
fbReset2(Axis := Axis2, Execute := bReset2);
IF bStatusPrev1 AND NOT fbPower1.Status AND bEnable1 THEN
    bStatusDropped1 := TRUE;
END_IF
bStatusPrev1 := fbPower1.Status;

// Axis1 commands.
fbMoveA(Axis := Axis1, Execute := bMoveA, Position := fPosA, Velocity := fVelo,
        Acceleration := fAcc, Deceleration := fDec);
fbMoveB(Axis := Axis1, Execute := bMoveB, Position := fPosB, Velocity := fVelo,
        Acceleration := fAcc, Deceleration := fDec);
fbMoveVelo(Axis := Axis1, Execute := bMoveVelo, Velocity := fVelo,
           Acceleration := fAcc, Deceleration := fDec,
           Direction := MC_Direction.MC_Positive_Direction);
fbHalt1(Axis := Axis1, Execute := bHalt1, Deceleration := fHaltDec1);
fbStop1(Axis := Axis1, Execute := bStop1, Deceleration := fStopDec1);
fbSetPos1(Axis := Axis1, Execute := bSetPos1, Position := fSetPos1,
          Mode := bSetPosRelative1);
fbHome1(Axis := Axis1, Execute := bHome1, Position := fHomePos1,
        HomingMode := eHomeMode1, bCalibrationCam := bCam1);

// C3: the deceleration MC_Halt really used = the peak |set acceleration| of its ramp.
rtHalt1(CLK := bHalt1);
IF rtHalt1.Q THEN
    fPeakDecel1 := 0;
END_IF
IF fbHalt1.Busy AND ABS(Axis1.NcToPlc.SetAcc) > fPeakDecel1 THEN
    fPeakDecel1 := ABS(Axis1.NcToPlc.SetAcc);
END_IF

// C2: how long MC_Stop keeps the axis after its Execute falls.
ftStop1(CLK := bStop1);
IF ftStop1.Q THEN
    nStopRelease := 0;
    bStopCounting := TRUE;
END_IF
IF bStopCounting THEN
    IF fbStop1.Busy THEN
        nStopRelease := nStopRelease + 1;
    ELSE
        bStopCounting := FALSE;
    END_IF
END_IF

// Coupling: Axis1 master, Axis2 slave.
fbGearIn(Master := Axis1, Slave := Axis2, Execute := bGearIn,
         RatioNumerator := fRatio, RatioDenominator := 1);
fbGearOut(Slave := Axis2, Execute := bGearOut);
fbGearInDyn(Master := Axis1, Slave := Axis2, Enable := bGearInDyn,
            GearRatio := fRatio, Acceleration := fAcc, Deceleration := fDec);
fbMoveSlave(Axis := Axis2, Execute := bMoveSlave, Position := fPosSlave,
            Velocity := fVelo, Acceleration := fAcc, Deceleration := fDec);
fbHalt2(Axis := Axis2, Execute := bHalt2, Deceleration := fHaltDec2);
fbPhasing(Master := Axis1, Slave := Axis2, Execute := bPhasing,
          PhaseShift := fPhaseShift, Velocity := fVelo,
          Acceleration := fAcc, Deceleration := fDec);

rtHalt2(CLK := bHalt2);
IF rtHalt2.Q THEN
    fPeakDecel2 := 0;
END_IF
IF fbHalt2.Busy AND ABS(Axis2.NcToPlc.SetAcc) > fPeakDecel2 THEN
    fPeakDecel2 := ABS(Axis2.NcToPlc.SetAcc);
END_IF

IF NOT bCamTableReady THEN                                      // CAM
    FOR i := 0 TO 36 DO                                         // CAM
        aCamTable[i, 0] := INT_TO_LREAL(i) * 10.0;              // CAM master
        aCamTable[i, 1] := INT_TO_LREAL(i) * 10.0;              // CAM slave
    END_FOR                                                     // CAM
    stCamRef.pArray := ADR(aCamTable);                          // CAM
    stCamRef.ArraySize := SIZEOF(aCamTable);                    // CAM
    stCamRef.TableType := MC_TableType.MC_TABLETYPE_EQUIDISTANT; // CAM
    stCamRef.NoOfRows := 37;                                    // CAM
    stCamRef.NoOfColumns := 2;                                  // CAM
    bCamTableReady := TRUE;                                     // CAM
END_IF                                                          // CAM
fbCamSelect(Master := Axis1, Slave := Axis2,                    // CAM
            CamTable := stCamRef, Execute := bCamSelect,       // CAM
            Periodic := FALSE, CamTableID := 1);                // CAM
fbCamIn(Master := Axis1, Slave := Axis2, Execute := bCamIn,    // CAM
        MasterOffset := fMasterOffset, SlaveOffset := fSlaveOffset, // CAM
        MasterScaling := fMasterScaling, SlaveScaling := fSlaveScaling, // CAM
        StartMode := MC_StartMode.MC_STARTMODE_ABSOLUTE,        // CAM
        CamTableID := 1);                                       // CAM
fbCamOut(Slave := Axis2, Execute := bCamOut);                   // CAM

// A3: what the running NC holds for the parameters an .xti may leave out.
fbAllowSlave1(Axis := Axis1, Enable := TRUE, ReadMode := E_ReadMode.READMODE_CYCLIC,
              ParameterNumber := MC_AxisParameter.AxisAllowMotionCmdToSlaveAxis);
fbAllowSlave2(Axis := Axis2, Enable := TRUE, ReadMode := E_ReadMode.READMODE_CYCLIC,
              ParameterNumber := MC_AxisParameter.AxisAllowMotionCmdToSlaveAxis);
fbLagMon1(Axis := Axis1, Enable := TRUE, ReadMode := E_ReadMode.READMODE_CYCLIC,
          ParameterNumber := MC_AxisParameter.AxisEnPositionLagMonitoring);
fbLagMon2(Axis := Axis2, Enable := TRUE, ReadMode := E_ReadMode.READMODE_CYCLIC,
          ParameterNumber := MC_AxisParameter.AxisEnPositionLagMonitoring);
fbAllowExt1(Axis := Axis1, Enable := TRUE, ReadMode := E_ReadMode.READMODE_CYCLIC,
            ParameterNumber := MC_AxisParameter.AxisAllowMotionCmdToExtSetAxis);

// Latch the first error of every block and axis, and every CommandAborted.
IF fbPower1.Error AND nErrPower1 = 0 THEN nErrPower1 := fbPower1.ErrorID; END_IF
IF fbPower2.Error AND nErrPower2 = 0 THEN nErrPower2 := fbPower2.ErrorID; END_IF
IF fbReset1.Error AND nErrReset1 = 0 THEN nErrReset1 := fbReset1.ErrorID; END_IF
IF fbMoveA.Error AND nErrMoveA = 0 THEN nErrMoveA := fbMoveA.ErrorID; END_IF
IF fbMoveB.Error AND nErrMoveB = 0 THEN nErrMoveB := fbMoveB.ErrorID; END_IF
IF fbMoveVelo.Error AND nErrMoveVelo = 0 THEN nErrMoveVelo := fbMoveVelo.ErrorID; END_IF
IF fbHalt1.Error AND nErrHalt1 = 0 THEN nErrHalt1 := fbHalt1.ErrorID; END_IF
IF fbStop1.Error AND nErrStop1 = 0 THEN nErrStop1 := fbStop1.ErrorID; END_IF
IF fbSetPos1.Error AND nErrSetPos1 = 0 THEN nErrSetPos1 := fbSetPos1.ErrorID; END_IF
IF fbHome1.Error AND nErrHome1 = 0 THEN nErrHome1 := fbHome1.ErrorID; END_IF
IF fbGearIn.Error AND nErrGearIn = 0 THEN nErrGearIn := fbGearIn.ErrorID; END_IF
IF fbGearOut.Error AND nErrGearOut = 0 THEN nErrGearOut := fbGearOut.ErrorID; END_IF
IF fbGearInDyn.Error AND nErrGearInDyn = 0 THEN nErrGearInDyn := fbGearInDyn.ErrorID; END_IF
IF fbMoveSlave.Error AND nErrMoveSlave = 0 THEN nErrMoveSlave := fbMoveSlave.ErrorID; END_IF
IF fbHalt2.Error AND nErrHalt2 = 0 THEN nErrHalt2 := fbHalt2.ErrorID; END_IF
IF fbPhasing.Error AND nErrPhasing = 0 THEN nErrPhasing := fbPhasing.ErrorId; END_IF
IF fbCamSelect.Error AND nErrCamSelect = 0 THEN nErrCamSelect := fbCamSelect.ErrorID; END_IF // CAM
IF fbCamIn.Error AND nErrCamIn = 0 THEN nErrCamIn := fbCamIn.ErrorID; END_IF          // CAM
IF Axis1.Status.Error AND nAxisErr1 = 0 THEN nAxisErr1 := Axis1.Status.ErrorId; END_IF
IF Axis2.Status.Error AND nAxisErr2 = 0 THEN nAxisErr2 := Axis2.Status.ErrorId; END_IF
bAbortedA := bAbortedA OR fbMoveA.CommandAborted;
bAbortedB := bAbortedB OR fbMoveB.CommandAborted;
bAbortedVelo := bAbortedVelo OR fbMoveVelo.CommandAborted;
bAbortedGearIn := bAbortedGearIn OR fbGearIn.CommandAborted;
bAbortedHome1 := bAbortedHome1 OR fbHome1.CommandAborted;
// ==== END IMPLEMENTATION ====
