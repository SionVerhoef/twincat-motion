# NC axis fixtures

Unmodified NC axis files from public sample projects, renamed only. All are simulated
axes; none comes from a real machine. Each project's licence is next to the files.

| File | Upstream | Licence |
|---|---|---|
| `spt_AxisHoming_Axis1.xti` | [Beckhoff-USA-Community/SPT_V4_Samples](https://github.com/Beckhoff-USA-Community/SPT_V4_Samples), `SPT_AxisHoming/_Config/NC/Axes/Axis 1.xti` | 0BSD, `LICENSE-SPT_V4_Samples` |
| `spt_ExternalSequence_Axis1.xti` | same repository, `SPT_ExternalSequence/_Config/NC/Axes/Axis 1.xti` | 0BSD, `LICENSE-SPT_V4_Samples` |
| `lcls_Axis_AxisParameter_Test.xti` | [pcdshub/lcls-twincat-motion](https://github.com/pcdshub/lcls-twincat-motion), `_Config/NC/Axes/Axis_AxisParameter_Test.xti` | BSD-3-Clause with grant-back, `LICENSE-lcls-twincat-motion.md` |
| `packml_VFFS_Seal.xti` | [Beckhoff-USA-Community/PackML_PLC_Example](https://github.com/Beckhoff-USA-Community/PackML_PLC_Example), `VFFS Demo PLC/_Config/NC/Axes/Seal.xti` | MIT, `LICENSE-PackML_Example` |

What each one is for:

- `spt_AxisHoming_Axis1`: an axis with nothing changed beyond the simulation defaults.
- `spt_ExternalSequence_Axis1`: the same kind of axis with three values set (scaling
  numerator, soft limit maximum enabled and its value), so the pair is a known diff.
- `lcls_Axis_AxisParameter_Test`: a unit-test axis with many explicit values (dynamics,
  soft limits, lag monitoring window, encoder offset). Its values are test markers, not a
  tuning.
- `packml_VFFS_Seal`: velocities, dynamics, scaling and reference velocity all set, plus a
  non-ASCII unit name.
