# Attributions

What this skill was built from, and what each source gave it.

## Bundled third-party content

Only the four NC axis files in `tests/fixtures/xti/`, used unmodified as test fixtures, each
with its upstream licence next to it (rows below). Everything else is original prose, code or
tables written for this skill. `CLAUDE.md` says which licences may ship at all.

## Sources

| Source | What it contributed |
|---|---|
| Beckhoff Information System: TwinCAT 3 NC Error Codes | Read. Code numbers and family ranges stated as facts; a curated subset explained in original words with original advice. Each answer links to the family page. No text or tables reproduced. |
| Beckhoff documentation: Tc2_MC2 PLC library, TwinCAT NC PTP, Tc3_MC2_AdvancedHoming, Automation Interface | Read. Block behaviour, states, parameters and API names restated in original words in `references/`. No text, tables or figures reproduced. |
| PLCopen Function Blocks for Motion Control | Block names and state names used as identifiers. No text or figures reproduced; no conformance claimed. |
| [pyads](https://github.com/stlehmann/pyads) `errorcodes_nc.py` (MIT) | Used to cross-check code numbers and meanings. Nothing copied. |
| [SPT_V4_Samples](https://github.com/Beckhoff-USA-Community/SPT_V4_Samples) (0BSD) | Two NC axis files, unmodified, as test fixtures in `tests/fixtures/xti/`. Licence alongside. |
| [lcls-twincat-motion](https://github.com/pcdshub/lcls-twincat-motion) (BSD-3-Clause, SLAC) | One NC axis file, unmodified, as a test fixture. Licence alongside. |
| [PackML_PLC_Example](https://github.com/Beckhoff-USA-Community/PackML_PLC_Example) (MIT) | One NC axis file, unmodified, as a test fixture. Licence alongside. |
| [twincat-st](https://github.com/SionVerhoef/twincat-st) (MIT, same maintainer) | Tool. CI runs its `tcpou.py check` and `st_review.py --pedantic` on `templates/` from release v0.6.0. Not bundled. |

Identifiers (error codes, block and parameter names) are quoted as facts; everything else
is written for this skill.

## Trademarks

TwinCAT® and Beckhoff® are registered trademarks of and licensed by Beckhoff Automation
GmbH. EtherCAT® is a registered trademark and patented technology, licensed by Beckhoff
Automation GmbH, Germany. PLCopen® is a registered trademark of the association PLCopen.
CiA® is a registered EU trademark of CAN in Automation e.V. Other product names, such as
AX5000, AX8000, AM8000 and TwinSAFE, are trademarks of their owners.

All are used nominatively, to identify the technology this skill works with. None of these
organisations is affiliated with this project or endorses it. This project claims no
conformance to any of their specifications and uses none of their logos.
