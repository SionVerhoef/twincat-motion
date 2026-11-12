#!/usr/bin/env python3
"""Look up a TwinCAT NC error code (classic NC / Tc2_MC2) and say what to check.

    nc_error.py 0x4550                hex, as InfoSys and the XAE logger print it
    nc_error.py 16#4357 17744         IEC hex, or the decimal ErrorID a PLC watch shows
    nc_error.py 4358                  bare digits: four are read as hex, five as decimal
    nc_error.py 0x4550 --json         the same result for a program
    nc_error.py --list                every code this tool explains

A code is matched exactly. One that is not in the curated table gets its family, the
part of the family it falls in, and the InfoSys page for that family - never the
meaning of a neighbouring code: 0x4357 and 0x4358 differ by one and mean opposite
directions.

The table is a deliberately small selection: the codes that decide whether an axis
enables, moves, homes and stops. Code numbers are facts; every label and every piece
of advice here is original wording. Do not grow this into a copy of Beckhoff's full
list, even reworded (CLAUDE.md, 'What you may use'). Everything else is a link.

Standard library only, so it runs on an engineering PC with nothing but Python 3.8.
Output is ASCII so a legacy Windows console prints it unchanged.
"""
import argparse
import json
import re
import sys

INFOSYS = 'https://infosys.beckhoff.com/content/1033/tc3ncerrcode/'
INDEX = INFOSYS + 'index.html'

# --- Families -----------------------------------------------------------------------
#
# The high byte of an NC error code says which NC object raised it. 'action' is the
# usual way out for that family; 'ranges' splits a family into the kinds of error it
# holds, so an unknown code still says whether it is a bad parameter, a missing link
# or something that happened while the axis ran.

AXIS_ERROR_ACTION = ('Axis error: remove the cause, then MC_Reset (rising edge on Execute). '
                     'Re-enable with MC_Power afterwards if the controller dropped out.')

FAMILIES = {
    0x40: {
        'name': 'General', 'page': '513122571.html',
        'action': 'Mostly start-up and configuration: fix the configuration and activate '
                 'it again. MC_Reset does not cure a configuration error.',
    },
    0x41: {
        'name': 'Channel (NCI)', 'page': '513126155.html',
        'action': 'NCI interpolation channel. Outside this skill: NCI/CNC is not covered.',
    },
    0x42: {
        'name': 'Group (command and set-point generation)', 'page': '513129739.html',
        'action': 'Usually a rejected or failed motion command. If the axis itself shows '
                 'the error (MC_ReadStatus Error = TRUE), remove the cause and MC_Reset. '
                 'If only the function block reports it, fix the inputs and trigger again.',
    },
    0x43: {
        'name': 'Axis', 'page': '513133323.html', 'action': AXIS_ERROR_ACTION,
        'ranges': [(0x4300, 0x433F, 'parameter value rejected (configuration or MC_WriteParameter)'),
                   (0x4340, 0x434F, 'axis not fully created or linked at start-up'),
                   (0x4350, 0x43FF, 'raised while commanding or moving the axis')],
    },
    0x44: {
        'name': 'Encoder', 'page': '513136907.html', 'action': AXIS_ERROR_ACTION,
        'ranges': [(0x4400, 0x442F, 'parameter value rejected (configuration or MC_WriteParameter)'),
                   (0x4430, 0x443F, 'latch / touch-probe activation'),
                   (0x4440, 0x444F, 'encoder not fully created or linked at start-up'),
                   (0x4450, 0x44FF, 'raised while the axis runs: position, limits, I/O data')],
    },
    0x45: {
        'name': 'Controller', 'page': '513140491.html', 'action': AXIS_ERROR_ACTION,
        'ranges': [(0x4500, 0x453F, 'parameter value rejected (configuration or MC_WriteParameter)'),
                   (0x4540, 0x454F, 'controller not fully created or linked at start-up'),
                   (0x4550, 0x45FF, 'raised while the axis runs (lag monitoring, internal)')],
    },
    0x46: {
        'name': 'Drive', 'page': '4670612235.html',
        'action': AXIS_ERROR_ACTION + ' A fault latched inside the drive may also need the '
                 "drive's own reset (cia402-motion).",
        'ranges': [(0x4600, 0x462F, 'drive parameter or operating mode rejected'),
                   (0x4630, 0x463F, 'hardware diagnosis reported by the drive or terminal'),
                   (0x4640, 0x464F, 'drive not fully created or linked at start-up'),
                   (0x4650, 0x46FF, 'raised while the axis runs: drive state, cyclic data')],
    },
    0x4A: {
        'name': 'Table (cam and characteristic tables)', 'page': '513147659.html',
        'action': 'Table definition or use. Check the table and its coupling, then MC_Reset '
                 'the slave if it went to error.',
    },
    0x4B: {
        'name': 'NC-PLC (Tc2_MC2 function blocks)', 'page': '513151243.html',
        'action': 'Raised by the PLC library. The axis need not be in error itself. The '
                 'block output clears when Execute falls; fix the call and trigger again.',
    },
    0x4C: {
        'name': 'Kinematic transformation', 'page': None,
        'action': 'Kinematics (TF511x) are outside this skill (NC2 point-to-point only).',
    },
    0x81: {
        'name': 'MC3 / Advanced Motion Pack', 'page': '1521802123.html',
        'action': 'An MC3 (Tc3_Mc3*) or Advanced Motion Pack code. This skill covers classic '
                 'NC with Tc2_MC2 only; MC3 behaves differently even where block names match.',
    },
}

# --- Curated codes ------------------------------------------------------------------
#
# label: a few words. meaning: what happened, in plain terms. check: what to look at,
# most likely first. handoff: the sibling skill that owns the next step, if any.

CODES = {
    # General
    0x4002: {
        'label': 'NC retain data could not be loaded',
        'meaning': 'At start-up the NC could not restore its persistent data. Axes that '
                   'rely on it (absolute encoders with multiturn overflow, stored '
                   'reference state) come up not homed.',
        'check': ['Expected on the very first start after retain data was switched on, or '
                  'after a new configuration; it should not repeat.',
                  'If it repeats: the retain storage on the controller (UPS / NOVRAM '
                  'setup) and the SAF task retain setting.',
                  'Your application must test Homed before it trusts the position.'],
    },

    # Group
    0x4216: {
        'label': 'Cam table unknown',
        'meaning': 'A coupling or characteristic refers to a table ID the NC does not have.',
        'check': ['CamTableID on MC_CamIn: the ID from the cam editor, or the one passed '
                  'to MC_CamTableSelect.',
                  'A PLC-built table: did MC_CamTableSelect finish with Done before '
                  'MC_CamIn started?'],
    },
    0x421B: {
        'label': 'Gear ratio of zero',
        'meaning': 'The coupling was started with a ratio of 0, which the NC refuses.',
        'check': ['RatioNumerator / GearRatio: an input left at its default of 0.',
                  'MC_GearIn: for a fractional ratio put the LREAL in the numerator, '
                  'denominator 1.'],
    },
    0x4221: {
        'label': 'Commanded velocity rejected',
        'meaning': 'The velocity of the move is outside what the axis accepts: zero or '
                   'less, above the maximum velocity, or above the reference velocity.',
        'check': ['The Velocity input against the axis maximum and reference velocity.',
                  'Units: the input is in axis units per second, not percent or rpm.'],
    },
    0x4222: {
        'label': 'Target position rejected (master)',
        'meaning': 'The target of the move cannot be used as given.',
        'check': ['Software end limits: is the target outside them?',
                  'Modulo axes: is the target inside the modulo range the block expects?',
                  'A target that is uninitialised, NaN or absurdly large.'],
    },
    0x4223: {
        'label': 'Controller or feed enable missing at start (master)',
        'meaning': 'A move was started on an axis whose controller enable or direction '
                   'enable was not set. Not the same as 0x4225, where the drive is the '
                   'one not ready.',
        'check': ['MC_Power: Enable, Enable_Positive and Enable_Negative all TRUE. '
                  'MC_Power.Status can be TRUE with both direction enables FALSE.',
                  'Start moves only after MC_Power.Status is TRUE.',
                  'Observed (4024.55, Tc2_MC2 3.3.59, simulated axis): a missing direction '
                  'enable gave this code on the move block for either direction, with no '
                  'axis error and no MC_Reset needed; 0x4357 / 0x4358 did not appear.'],
    },
    0x422A: {
        'label': 'Controller or feed enable missing at start (slave)',
        'meaning': 'Same as 0x4223, for the slave of a coupling.',
        'check': ['MC_Power with all three enables on the slave axis as well as the master.'],
    },
    0x4225: {
        'label': 'Drive not ready when the move started',
        'meaning': 'The NC had controller enable, but the drive did not report itself '
                   'ready. Not the same as 0x4223, where the enable itself is missing.',
        'check': ['Drive state machine: is it in Operation enabled? If not, why '
                  '(cia402-motion).',
                  'Hardware enable / STO input. Never bridge it in software.',
                  'NC drive type matches the device, and the drive status word is linked '
                  'to the NC drive input.'],
        'handoff': 'cia402-motion',
    },
    0x4231: {
        'label': 'Velocity of zero or less',
        'meaning': 'A move was commanded with a velocity of 0 or a negative value.',
        'check': ['The Velocity input of the move block. Direction comes from the target '
                  'or the Direction input, never from the sign of Velocity.',
                  'MC_MoveAbsolute with Velocity 0 returned 0x4359 instead in one test '
                  '(4024.55, Tc2_MC2 3.3.59).'],
    },
    0x4243: {
        'label': 'Superimposed move only partly done',
        'meaning': 'Usually a warning, not an axis error: MC_MoveSuperImposed could not fit '
                   'the whole Distance into the allowed Length and VelocityDiff and did '
                   'as much as it could.',
        'check': ['ActualDistance against Distance: how much is missing.',
                  'More Length, more VelocityDiff, or a mode that reduces length instead '
                  'of velocity.',
                  'Decide in the application whether a partial correction is acceptable.'],
    },
    0x4245: {
        'label': 'Superimposed move refused',
        'meaning': 'A superimposed move could not start: one is already running, or the '
                   'axis is not moving.',
        'check': ['A superimposed move needs a moving axis; on a standing axis use an '
                  'ordinary move.',
                  'Wait for the previous MC_MoveSuperImposed Done, or MC_AbortSuperposition.'],
    },
    0x424A: {
        'label': 'Master standing still, cannot synchronise',
        'meaning': 'A coupling that synchronises on the fly (flying saw) needs a moving '
                   'master; the master velocity is zero.',
        'check': ['Start the master first, or couple at standstill with MC_GearIn.'],
    },
    0x4242: {
        'label': 'A stop is already running',
        'meaning': 'A command arrived while the axis is still executing a stop.',
        'check': ['Wait for the stop to finish (MC_Stop / MC_Halt Done) before the next '
                  'command.', 'See 0x42EF for the MC_Stop lock.'],
    },
    0x425A: {
        'label': 'Coupling refused while an axis is still moving',
        'meaning': 'This kind of coupling needs standstill, and the master or the slave '
                   'still has a motion command running.',
        'check': ['Is the master moving? MC_GearIn onto a master at constant velocity was '
                  'refused with this code (4024.55, Tc2_MC2 3.3.59), slave at standstill.',
                  'Halt the slave and wait for standstill before MC_GearIn.',
                  'To catch a moving axis use MC_GearInMultiMaster with '
                  'AdvancedSlaveDynamics, or the flying-saw blocks.'],
    },
    0x4251: {
        'label': 'Function not available here',
        'meaning': 'The NC does not provide the requested function, or not for this axis '
                   'or coupling.',
        'check': ['Phasing: MC_PhasingRelative on an MC_GearInDyn slave gave this code. '
                  'Phase on MC_GearIn or a cam coupling instead (references/coupling.md).',
                  'The block and library version against what the axis supports.'],
    },
    0x4267: {
        'label': 'Command refused on a coupled slave',
        'meaning': 'A command that only a master may receive was sent to an axis that is '
                   'the slave of a coupling.',
        'check': ['Decouple first (MC_GearOut, MC_CamOut), or stop the master.',
                  'Seen for MC_Halt on a coupled slave with "Allow motion commands to slave '
                  'axis" FALSE; a move in the same state gives 0x4B08 instead.'],
    },
    0x425D: {
        'label': 'Axis stop already active',
        'meaning': 'The axis is executing a stop and refuses the command.',
        'check': ['Same as 0x4242: let the stop finish first; see 0x42EF for the '
                  'MC_Stop lock.'],
    },
    0x42EF: {
        'label': 'Axis locked by MC_Stop',
        'meaning': 'MC_Stop keeps the axis locked for as long as its Execute stays TRUE. '
                   'Every other motion command is refused until then.',
        'check': ['Set MC_Stop.Execute FALSE after Done.',
                  'Use MC_Halt for an ordinary stop. Keep MC_Stop for stops that must '
                  'not be overridden.'],
    },
    0x4261: {
        'label': 'Cam table not found',
        'meaning': 'The table ID given does not exist, or is not unique.',
        'check': ['As 0x4216: the CamTableID, and that MC_CamTableSelect finished first.'],
    },
    0x4260: {
        'label': 'Controller enable lost',
        'meaning': 'The controller enable was missing at start or dropped while the axis '
                   'moved.',
        'check': ['MC_Power.Enable is held TRUE and MC_Power is called every cycle.',
                  'The PLC task stalled or stopped, so the enable was not refreshed '
                  '(overrun, a long loop, a breakpoint). One field case was an unbounded '
                  'loop that only ran long after hours.'],
    },
    0x4292: {
        'label': 'Command buffer full',
        'meaning': 'More motion commands were queued than the axis can buffer.',
        'check': ['Queue a buffered command only after the previous one is Active.',
                  'BufferMode on each block: the default, Aborting, needs no buffer.'],
    },
    0x4296: {
        'label': 'New command contradicts the running one',
        'meaning': 'A buffered or blended command would need a direction that does not fit '
                   'the command before it, so it is refused. A blending position beyond '
                   'the previous target does this.',
        'check': ['Blending position: it must lie before the previous target.',
                  'Buffer mode and target of the second command against the first.'],
    },
    0x429C: {
        'label': 'Homing: reference cam not found',
        'meaning': 'NC homing searched for the reference cam and did not see it.',
        'check': ['The cam signal reaches the PLC and is passed to MC_Home '
                  '(bCalibrationCam).',
                  'Cam search direction and homing velocity in the encoder parameters.',
                  'Wiring and sensor polarity.'],
    },
    0x429D: {
        'label': 'Homing: reference cam not released',
        'meaning': 'NC homing reached the cam but never saw it switch off again.',
        'check': ['Cam polarity (a normally closed sensor looks permanently active).',
                  'Search direction away from the cam; the cam being longer than '
                  'expected.'],
    },
    0x429E: {
        'label': 'Homing: sync pulse not found',
        'meaning': 'After the cam, NC homing waited for the encoder reference pulse and '
                   'did not get it.',
        'check': ['Latch / reference-pulse setup on the encoder terminal or drive.',
                  'Encoder type has a reference pulse at all; reference mode in the '
                  'encoder parameters matches.'],
    },
    0x42A0: {
        'label': 'Follow-on error (group)',
        'meaning': 'This axis stopped because another axis it is coupled or grouped with '
                   'went to error.',
        'check': ['Find the first error on the other axis (master, coupled axis) and fix '
                  'that; this code is only the consequence.'],
    },

    # Axis
    0x4356: {
        'label': 'Controller enable missing',
        'meaning': 'A move was commanded while the axis controller was not enabled.',
        'check': ['MC_Power.Enable TRUE and MC_Power.Status TRUE before any move.'],
    },
    0x4357: {
        'label': 'Feed enable minus missing',
        'meaning': 'The axis may not move in the negative direction: '
                   'MC_Power.Enable_Negative is FALSE. (0x4358 is the positive direction.)',
        'check': ['MC_Power.Enable_Negative TRUE.',
                  'If a limit switch drives it: is the axis on the negative limit?'],
    },
    0x4358: {
        'label': 'Feed enable plus missing',
        'meaning': 'The axis may not move in the positive direction: '
                   'MC_Power.Enable_Positive is FALSE. (0x4357 is the negative direction.)',
        'check': ['MC_Power.Enable_Positive TRUE.',
                  'If a limit switch drives it: is the axis on the positive limit?'],
    },
    0x4359: {
        'label': 'Positioning velocity rejected',
        'meaning': 'The velocity of a positioning move is zero or less, or above the maximum '
                   'or reference velocity of the axis.',
        'check': ['The Velocity input: an input left at 0 is the usual cause.',
                  'The axis maximum and reference velocity (axis-parameters.md).',
                  'Seen for MC_MoveAbsolute with Velocity 0 (4024.55, Tc2_MC2 3.3.59), '
                  'where 0x4231 might be expected.'],
    },
    0x435C: {
        'label': 'Did not settle in the target window in time',
        'meaning': 'The set-point reached the target but the actual position did not stay '
                   'inside the target window before the PEH monitoring time ran out.',
        'check': ['Target position window and time, and the PEH monitoring time.',
                  'Mechanics: friction, backlash, a load hanging on the axis.',
                  'Tuning; in CSP the loop that matters is in the drive.',
                  'Record SetPos / ActPos / PosDiff (twincat-scope).'],
        'handoff': 'twincat-scope',
    },
    0x435D: {
        'label': 'Commanded motion not seen at the encoder',
        'meaning': 'The axis was told to move but its actual position did not change as '
                   'expected within the motion-monitoring time.',
        'check': ['Brake still closed; drive producing no torque.',
                  'Encoder not counting, or linked to the wrong input.',
                  'Encoder and drive scaled differently.'],
    },
    0x43A0: {
        'label': 'Follow-on error (axis)',
        'meaning': 'This axis went to error because a coupled or related axis did.',
        'check': ['Read the error of the master or the other axis first; that is the cause.'],
    },

    # Encoder
    0x4420: {
        'label': 'Software limit (min) monitoring parameter invalid',
        'meaning': 'The configuration of the minimum software end position is not accepted.',
        'check': ['Minimum software limit value and enable in the encoder parameters, '
                  'including min below max.'],
    },
    0x4421: {
        'label': 'Software limit (max) monitoring parameter invalid',
        'meaning': 'The configuration of the maximum software end position is not accepted.',
        'check': ['Maximum software limit value and enable in the encoder parameters, '
                  'including max above min.'],
    },
    0x4422: {
        'label': 'Set position out of range',
        'meaning': 'A new actual position was set (MC_SetPosition, homing) that the encoder '
                   'cannot represent.',
        'check': ['The Position input of MC_SetPosition; modulo range; encoder mask and '
                  'scaling.'],
    },
    0x4450: {
        'label': 'Encoder counter underflow',
        'meaning': 'The incremental counter behind the encoder value ran out of range '
                   'downwards.',
        'check': ['Encoder mask (maximum count) against the real counter width of the '
                  'terminal or drive.', 'An axis that keeps travelling one way.'],
    },
    0x4451: {
        'label': 'Encoder counter overflow',
        'meaning': 'The incremental counter behind the encoder value ran out of range '
                   'upwards.',
        'check': ['As 0x4450: encoder mask against the counter width; an axis that keeps '
                  'travelling one way.'],
    },
    0x4460: {
        'label': 'Below the minimum software limit at start',
        'meaning': 'The axis is, or the target is, below the minimum software end position '
                   'as the move starts.',
        'check': ['Actual position against the limit: move the axis back in the allowed '
                  'direction.', 'The limit value; the axis being homed at all.'],
    },
    0x4461: {
        'label': 'Above the maximum software limit at start',
        'meaning': 'The axis is, or the target is, above the maximum software end position '
                   'as the move starts.',
        'check': ['Actual position against the limit: move the axis back in the allowed '
                  'direction.', 'The limit value; the axis being homed at all.'],
    },
    0x4462: {
        'label': 'Minimum software limit reached while moving',
        'meaning': 'During the move the axis ran into the minimum software end position.',
        'check': ['The target; a jog or velocity move that has no end; the limit value.'],
    },
    0x4463: {
        'label': 'Maximum software limit reached while moving',
        'meaning': 'During the move the axis ran into the maximum software end position.',
        'check': ['The target; a jog or velocity move that has no end; the limit value.'],
    },
    0x4464: {
        'label': 'Encoder hardware error',
        'meaning': 'The encoder input (terminal or drive) reports a hardware fault.',
        'check': ['Diagnosis of the terminal or drive that provides the encoder value: '
                  'cable, supply, encoder itself.'],
    },
    0x4465: {
        'label': 'Position could not be initialised at start-up',
        'meaning': 'At start-up the NC could not get a starting position inside the '
                   'expected range, however often it tried.',
        'check': ['Encoder position-initialisation settings and the range they expect.',
                  'Absolute encoder offset and multiturn handling (NC retain data).',
                  'The encoder actually delivering a position at boot.'],
    },
    0x4466: {
        'label': 'Encoder input data invalid for too long',
        'meaning': 'The process data carrying the encoder value was invalid for more '
                   'cycles than allowed. Almost always a bus problem.',
        'check': ['Working counter / WcState of the slave and its EtherCAT state (OP).',
                  'This is where ethercat-diagnostics takes over.'],
        'handoff': 'ethercat-diagnostics',
    },
    0x4467: {
        'label': 'Actual position invalid',
        'meaning': 'The encoder delivered a position flagged as not valid.',
        'check': ['Error or invalid bits in the encoder status of the terminal or drive, '
                  'for example an input PDO flagged invalid.',
                  'Absolute encoders after a fault or power cycle.'],
    },

    # Controller
    0x4550: {
        'label': 'Position lag too large',
        'meaning': 'The difference between set and actual position stayed above the lag '
                   'limit for longer than the filter time.',
        'check': ['Is the mechanics free? Binding, a brake, a crash.',
                  'Dynamics higher than motor and drive can follow (current limit).',
                  'Encoder and drive scaling consistent; reference velocity right for a '
                  'velocity-mode drive.',
                  'Record SetPos / ActPos / PosDiff (twincat-scope) before touching the '
                  'limit. Widening it, or switching monitoring off, only hides the fault.'],
        'handoff': 'twincat-scope',
    },
    0x4551: {
        'label': 'Velocity lag too large',
        'meaning': 'The difference between set and actual velocity stayed above its limit '
                   'for longer than the filter time.',
        'check': ['Same causes as 0x4550: mechanics, dynamics, scaling, reference velocity.',
                  'Record SetVelo / ActVelo (twincat-scope).'],
        'handoff': 'twincat-scope',
    },

    # Drive
    0x4626: {
        'label': 'Function not supported by this drive (or now)',
        'meaning': 'The drive or axis type cannot do the requested function, or not in its '
                   'current state.',
        'check': ['Whether this drive type supports it at all (ethercat-esi / the drive '
                  'documentation).',
                  'Simulation axes: MC_TorqueControl was reported to give this on older '
                  '4024 builds.'],
    },
    0x4630: {'label': 'Drive or terminal overtemperature',
             'meaning': 'The drive or terminal reports it is too hot.',
             'check': ['Cooling, ambient temperature, current / duty cycle.']},
    0x4631: {'label': 'Drive or terminal undervoltage',
             'meaning': 'The supply to the drive or terminal is too low.',
             'check': ['Power supply and its wiring; supply dips when the motor accelerates.']},
    0x4632: {'label': 'Wire break, phase A',
             'meaning': 'The drive sees an open circuit on motor phase A.',
             'check': ['Motor cable and connectors on phase A.']},
    0x4633: {'label': 'Wire break, phase B',
             'meaning': 'The drive sees an open circuit on motor phase B.',
             'check': ['Motor cable and connectors on phase B.']},
    0x4634: {'label': 'Overcurrent, phase A',
             'meaning': 'The current on motor phase A exceeded the limit.',
             'check': ['Short circuit in cable or motor; current setting against the motor.']},
    0x4635: {'label': 'Overcurrent, phase B',
             'meaning': 'The current on motor phase B exceeded the limit.',
             'check': ['Short circuit in cable or motor; current setting against the motor.']},
    0x4636: {'label': 'Torque overload or stall',
             'meaning': 'The drive or terminal detected an overload or a stalled motor.',
             'check': ['Mechanics blocked; load too high for the current setting; '
                       'acceleration too high (steppers lose steps).']},
    0x4650: {
        'label': 'Drive dropped out of ready',
        'meaning': 'The drive reports itself not ready while the NC needs it: in fault, '
                   'still starting up, or without its enable.',
        'check': ["The drive's own fault code (cia402-motion for CoE drives).",
                  'Hardware enable / STO. Never bridge it in software.',
                  'DC link / power supply.'],
        'handoff': 'cia402-motion',
    },
    0x4651: {
        'label': 'Cyclic communication with the drive failed',
        'meaning': 'The NC stopped getting valid cyclic data from the drive.',
        'check': ['EtherCAT state of the drive, working counter, sync / watchdog errors '
                  '(ethercat-diagnostics).'],
        'handoff': 'ethercat-diagnostics',
    },
    0x4655: {
        'label': 'Drive input data invalid for too long',
        'meaning': 'The process data from the drive was invalid for more cycles than '
                   'allowed. Almost always a bus problem.',
        'check': ['Working counter / WcState of the slave and its EtherCAT state (OP) '
                  '(ethercat-diagnostics).'],
        'handoff': 'ethercat-diagnostics',
    },

    # Table
    0x4A00: {
        'label': 'Table ID not allowed',
        'meaning': 'The ID for a new table is already in use or outside 1..255.',
        'check': ['MC_CamTableSelect: an ID that a cam-editor table or an earlier select '
                  'already uses. Keep PLC table IDs apart from editor IDs.'],
    },
    0x4A06: {
        'label': 'Table not monotonic',
        'meaning': 'The master column of the table does not rise steadily, or does not fit '
                   'the step size given.',
        'check': ['A PLC-built position table: master values must strictly ascend; look '
                  'for duplicates, unfilled rows at the end of the array, or a NoOfRows '
                  'larger than the rows you filled.'],
    },

    # NC-PLC
    0x4B06: {
        'label': 'Function block input invalid',
        'meaning': 'One of the inputs of the Tc2_MC2 block has a value it does not accept.',
        'check': ['Every input of the block: out-of-range values such as an override '
                  'above 100 %, a gear ratio with denominator 0, enums and parameter '
                  'numbers.'],
    },
    0x4B07: {
        'label': 'Function block timed out waiting for the axis',
        'meaning': 'The block waited for the NC to confirm the end of the command, for '
                   'example the axis settling in its target window, and gave up.',
        'check': ['Target position window and time: does the axis ever settle there?',
                  'Tuning and mechanics, as for 0x435C.'],
    },
    0x4B08: {
        'label': 'Axis is in protected mode',
        'meaning': 'The axis refuses direct motion commands, typically because it is the '
                   'slave of a coupling.',
        'check': ['Decouple first (MC_GearOut, MC_CamOut), then command it.',
                  'MC_ReadStatus: ProtectedMode and the coupling state.',
                  'The axis parameter "Allow motion commands to slave axis" is FALSE here '
                  '(also when absent from the .xti). Set TRUE, a move decouples the slave '
                  'instead of failing.',
                  'MC_Halt on such a slave gives 0x4267, not this code.'],
    },
    0x4B09: {
        'label': 'Axis not ready',
        'meaning': 'The block found the axis not ready for the command.',
        'check': ['MC_Power.Status TRUE.',
                  'MC_ReadStatus: is the axis in error? Clear it with MC_Reset first.'],
    },
    0x4B0A: {
        'label': 'Homing failed',
        'meaning': 'MC_Home ended in error. Usually the real cause is the axis error '
                   'behind it.',
        'check': ['MC_ReadAxisError / the axis ErrorID after the failure: often 0x429C, '
                  '0x429D or 0x429E.',
                  'Axis error 0: was the homing aborted? MC_Halt during MC_Home ends it '
                  'with this code (not CommandAborted) and leaves the axis not homed; '
                  'a new MC_Home starts without MC_Reset.'],
    },
    0x4B0E: {
        'label': 'Required TwinCAT function not available',
        'meaning': 'The block needs a separately licensed TwinCAT function that is not '
                   'installed or licensed on the target.',
        'check': ['Licences on the target (for example TF5050 for camming).'],
    },
    0x4B42: {
        'label': 'Axis is enabled',
        'meaning': 'The function only works with the axis disabled.',
        'check': ['Switch MC_Power off, wait for Status FALSE, then call the function.'],
    },
    0x4B60: {
        'label': 'Motion command never became active',
        'meaning': 'The block issued its command but the NC never reported it running.',
        'check': ['A buffered command whose predecessor ended in error or was aborted.',
                  'Axis error or lost enable at the moment of the start.'],
    },
    0x4B62: {
        'label': 'Buffered command ended in error',
        'meaning': 'A buffered command ended in error, but the axis had already moved on '
                   'to the next command, so its own error number is lost.',
        'check': ['The axis error history (MC_ReadAxisError, the XAE logger) for what '
                  'went wrong.'],
    },
    0x4B64: {
        'label': 'BufferMode not supported',
        'meaning': 'The block or the situation does not support the chosen BufferMode.',
        'check': ['BufferMode input; fall back to Aborting or Buffered.'],
    },
    0x4B66: {
        'label': 'Function block not called every cycle',
        'meaning': 'A busy Tc2_MC2 block was not called in every PLC cycle, so it could '
                   'not follow its command, and the NC had moved on without it.',
        'check': ['Call every motion block unconditionally each cycle, outside IF and '
                  'CASE branches (twincat-st owns this rule).'],
        'handoff': 'twincat-st',
    },
}


# --- The templates' own codes -------------------------------------------------------
#
# templates/*.TcPOU report their own errors above 16#FFFF, clear of every NC and ADS code.
# Kept in step with the cErr constants there (tests/test_nc_error.py checks it).

TEMPLATE_CODES = {
    0x00010001: ('FB_Axis', 'cErrNotIssued',
                 'A requested command waited too long and was never issued to the axis.'),
    0x00010101: ('FB_HomePlc', 'cErrParams', 'stParams not usable: check the values.'),
    0x00010102: ('FB_HomePlc', 'cErrMoveOffTime',
                 'The reference switch was not released in time while moving off it.'),
    0x00010103: ('FB_HomePlc', 'cErrSearchTime',
                 'The reference switch was not found in time: search direction, switch '
                 'wiring, or bRefSwitch not passed every cycle.'),
    0x00010104: ('FB_HomePlc', 'cErrStepTime', 'Halt, set position or homed mark too slow.'),
    0x00010105: ('FB_HomePlc', 'cErrAborted', 'Another command took over the axis.'),
    0x000101FF: ('FB_HomePlc', 'cErrInvalidState', 'Internal step error.'),
    0x00010201: ('FB_HomeNc', 'cErrParams', 'stParams not usable: check the values.'),
    0x00010202: ('FB_HomeNc', 'cErrTimeout',
                 'The homing run took longer than stParams.tTimeout; the axis was halted.'),
    0x00010203: ('FB_HomeNc', 'cErrAborted', 'Another command took over the axis.'),
    0x000102FF: ('FB_HomeNc', 'cErrInvalidState', 'Internal step error.'),
}
TEMPLATE_FAMILY = 'twincat-motion template (not an NC code)'


# --- Parsing ------------------------------------------------------------------------

def family_of(code):
    """Return (family_key, family) for an NC code, or (None, None)."""
    if 0x4000 <= code <= 0x4FFF or 0x8100 <= code <= 0x81FF:
        key = code >> 8
        return key, FAMILIES.get(key)
    return None, None


def in_nc_range(code):
    return 0x4000 <= code <= 0x4FFF or 0x8100 <= code <= 0x81FF


def parse(text):
    """Read a code as written by a person. Returns (value, how) or raises ValueError.

    0x / 16# prefix: hex. Letters a-f: hex. Bare digits: read both ways and keep the one
    that is an NC code; four digits land in hex, five in decimal, never both.
    """
    s = text.strip().replace('_', '')
    low = s.lower()
    if low.startswith('0x'):
        return int(low[2:], 16), 'hex'
    if low.startswith('16#'):
        return int(low[3:], 16), 'hex'
    if re.fullmatch(r'[0-9a-f]+', low) and re.search(r'[a-f]', low):
        return int(low, 16), 'hex'
    if not re.fullmatch(r'[0-9]+', low):
        raise ValueError('not a number: %r' % text)
    as_dec, as_hex = int(low, 10), int(low, 16)
    hits = [(v, how) for v, how in ((as_hex, 'hex'), (as_dec, 'decimal')) if in_nc_range(v)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        return as_dec, 'decimal'
    raise ValueError('ambiguous: %r is an NC code read as hex and as decimal' % text)


# --- Lookup -------------------------------------------------------------------------

def link(fam):
    return INFOSYS + fam['page'] if fam and fam.get('page') else INDEX


def lookup(text):
    value, how = parse(text)
    result = {'input': text, 'code': '0x%04X' % value, 'decimal': value, 'read_as': how}
    if 0x00010000 <= value <= 0x0001FFFF:
        result['family'] = TEMPLATE_FAMILY
        result['link'] = 'templates/README.md'
        entry = TEMPLATE_CODES.get(value)
        if entry:
            block, const, meaning = entry
            result['known'] = True
            result.update({'label': '%s.%s' % (block, const), 'meaning': meaning,
                           'check': ['Not an NC code. If the axis also has an error, '
                                     'look up the axis ErrorID separately.']})
        else:
            result['known'] = False
            result['note'] = ('In the range the templates use for their own codes, but not '
                              'one of them: check the cErr constants in your copy.')
        return result
    key, fam = family_of(value)
    if fam is None:
        result['known'] = False
        if key is not None:
            result['family'] = 'unassigned NC range'
            result['note'] = 'No NC error family uses this range. Check the number.'
        else:
            result['note'] = ('Not a TwinCAT NC error code (those are 0x4000-0x4FFF, and '
                              '0x81xx for MC3). Values below 0x4000 are usually ADS return '
                              'codes: look them up under "ADS Return Codes" in InfoSys.')
        result['link'] = INDEX
        return result

    result['family'] = fam['name']
    result['action'] = fam['action']
    result['link'] = link(fam)
    for lo, hi, kind in fam.get('ranges', []):
        if lo <= value <= hi:
            result['kind'] = kind
    entry = CODES.get(value)
    if entry:
        result['known'] = True
        result.update({k: entry[k] for k in ('label', 'meaning', 'check')})
        if 'handoff' in entry:
            result['handoff'] = entry['handoff']
    else:
        result['known'] = False
        result['note'] = ('Not in the curated table. Do not infer the meaning from a nearby '
                          'code; read it on the family page below.')
    return result


def render(r):
    lines = ['%s (decimal %d, read as %s)' % (r['code'], r['decimal'], r['read_as'])]
    if 'family' in r:
        lines.append('  family : ' + r['family'])
    if 'kind' in r:
        lines.append('  kind   : ' + r['kind'])
    if r.get('label'):
        lines.append('  error  : ' + r['label'])
        lines.append('  meaning: ' + r['meaning'])
        lines.append('  check  :')
        lines.extend('    - ' + c for c in r['check'])
    if r.get('note'):
        lines.append('  note   : ' + r['note'])
    if r.get('action'):
        lines.append('  action : ' + r['action'])
    if r.get('handoff'):
        lines.append('  next   : ' + r['handoff'] + ' skill')
    lines.append('  source : ' + r['link'])
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Explain a TwinCAT NC (Tc2_MC2) error code.',
        epilog='Bare digits: four are read as hex (4550), five as decimal (17744).')
    ap.add_argument('codes', nargs='*', help='error codes: 0x4550, 16#4550, 4550 or 17744')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    ap.add_argument('--list', action='store_true', help='list the curated codes')
    args = ap.parse_args(argv)

    if args.list:
        rows = [{'code': '0x%04X' % c, 'family': family_of(c)[1]['name'],
                 'label': CODES[c]['label']} for c in sorted(CODES)]
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for row in rows:
                print('%s  %-40s %s' % (row['code'], row['family'], row['label']))
        return 0
    if not args.codes:
        ap.error('give at least one code, or --list')

    results = []
    for text in args.codes:
        try:
            results.append(lookup(text))
        except ValueError as exc:
            ap.error(str(exc))
    if args.json:
        print(json.dumps(results if len(results) > 1 else results[0], indent=2))
    else:
        print('\n\n'.join(render(r) for r in results))
    return 0 if all('family' in r and r['family'] != 'unassigned NC range'
                    for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
