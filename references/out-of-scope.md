# Out of scope: what this skill does not cover

This skill covers classic TwinCAT NC point-to-point axes with `Tc2_MC2` (often called NC2).
The products below share block names or concepts with it but behave differently. Advice
written for NC2 is often wrong on them, so the first job is to **recognise them and say so**.

When a question lands here: name the product, say this skill does not cover it, keep to what
is genuinely the same (a single NC axis's configuration, a bus fault, the drive's state
machine), and point to that product's own documentation in the Beckhoff Information System.
Don't fill the gap from NC2 knowledge without labelling it as such.

## How to recognise them

| You see | It is |
|---|---|
| `Tc3_Mc3Base`, `Tc3_Mc3Ptp`, `Tc3_Mc3Camming`, `McToPlc` / `PlcToMc`, `EnablePositive` (no underscore), error codes 0x81xx (shared with the Advanced Motion Pack), axes under `_Config/Motion/`, `.xti` with class `CTComMcAxisDef` | **TwinCAT MC3** |
| G-code, an NCI interpreter, `Tc2_NCI`, axes in an interpolation channel | **NCI** (TF5100) or **CNC** (TF5200) |
| movers, `Tc3_XTS_Utility`, often with group blocks (`MC_Group*`) from coordinated motion | **XTS** (TF5850) |
| `Tc3_XPlanar*`, `Tc3_Mc3PlanarMotion`, planar movers and tracks | **XPlanar** (TF5890) |
| a kinematic group, a robot or delta kinematics, transformations between axis and Cartesian coordinates | **Kinematic Transformation** (TF511x) |
| collision avoidance between axes, pick-and-place, the Advanced Motion Pack | **TF5400**, **TF5410**, **TF5420** |
| hydraulic axes, valve characteristics | **hydraulic positioning** (TF5810; MC3 fluid power) |
| `Tc3_DriveMotionControl` | positioning inside the drive, without an NC axis |

## What to know about each

**TwinCAT MC3** (TF5500 and up). Beckhoff's successor to NC2, on TwinCAT 3.1.4026.23.1 or
later. Same `MC_` block names, but:
- no `Override` or `BufferMode` on `MC_Power`; override is a separate block, as a factor
  rather than a percentage
- homing modes are replaced by a homing-state block and homing objects
- typed axis references; its own tasks instead of SAF/SVB; its own error range
  (0x81xx, shared with the Advanced Motion Pack; `nc_error.py` names the family and does not explain the code)
- couplings and slave motion commands behave differently

MC3 and NC2 can run on the same controller, so check per axis. Mixing identifiers from the two
in one project is a common mistake in generated code.

**NCI / CNC.** Interpolated paths over several axes. Not reachable with PTP blocks and
buffer modes; buffered PTP moves on separate axes are not a path.

**XTS and XPlanar.** Movers are NC axes managed in groups, with their own libraries for
tracks, collision avoidance and motion. Single-axis PTP advice on a mover is wrong.

**Kinematics and the Advanced Motion Pack.** Separately licensed products with their own
configuration and blocks.

**`Tc3_DriveMotionControl`.** Uses block names such as `MC_Home` and `MC_HomingMode` with a
different meaning: its homing enum has values that `Tc2_MC2` does not (for example a block
mode). Check which library an `MC_` identifier comes from before applying anything on the
other pages.

**Also not covered:** Motion Designer sizing (TE5910), drive tuning inside the drive
(Drive Manager 2, TE5960 autotuning; this skill only says *that* a CSP axis is tuned there),
and safety functions (`boundaries.md`).
