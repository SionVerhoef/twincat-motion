# Field test results

Copy this file to `research/field-test-results.md` (gitignored) and fill it in. Protocol:
`evals/field-test/README.md`. No identities: no NetIDs, IP or MAC addresses, host or user
names, local paths, serial numbers or licence keys.

## Setup

| | |
|---|---|
| Date | |
| TwinCAT build (XAE and runtime) | |
| `Tc2_MC2` version | |
| `Tc2_MC2_Camming` version, licence | |
| Runtime on | local PC in run mode / test IPC (model only) |
| NC SAF cycle time | |
| PLC task cycle time | |
| Drive in section G (product name only) | |

## Results

Status: `CONFIRMED`, `DIFFERENT`, `PARTIAL` or `NOT RUN`. Under Observed, give codes in hex as
XAE shows them, values with units, and what `nc_error.py` said for each code.

| ID | Check | Status | Observed |
|---|---|---|---|
| A1 | What a new axis writes to its file | | |
| A2 | XAE and a hand-edited `.xti` | | |
| A3 | What an absent attribute means | | |
| A4.1 | Time Compensation: XAE field → `.xti` path | | |
| A4.2 | External set-point axis setting → `.xti` path | | |
| A4.3 | Motion commands to slaves FALSE → `.xti` path | | |
| A4.4 | Position lag monitoring off → `.xti` path | | |
| A5 | `axis-change.ps1` produce and apply | | |
| A6 | Flying saw library and product number | | |
| A7 | NC retain settings: menu path and option names | | |
| B1 | Templates compile | | |
| B2 | `PRG_FieldTest` compiles | | |
| B3 | Example program copy, links, activation | | |
| C0 | Runtime parameter values | | |
| C1 | `MC_Power` with only `Enable` | | |
| C2 | `MC_Stop` lock and release | | |
| C3 | `MC_Halt` with deceleration 0 (runs a–d) | | |
| C4 | Which commands set homed | | |
| C5 | Default homing; `MC_Halt` during `MC_Home` | | |
| C6 | Override | | |
| C7 | Zero velocity, zero acceleration | | |
| C8 | Retargeting a running move | | |
| D1 | `FB_Axis` power and reset | | |
| D2 | `FB_HomePlc` runs 1–4 | | |
| D3 | `FB_Axis` moves 1–5 | | |
| D4 | `FB_HomeNc` runs 1–2 | | |
| E1 | Move on a slave, commands allowed | | |
| E2 | Decoupling a moving slave | | |
| E3 | `MC_Halt` 0 on a decoupled slave | | |
| E4 | `MC_GearInDyn` Enable FALSE | | |
| E5 | `MC_CamIn` off the table position; formula | | |
| E6 | Phasing on CamIn / GearIn / GearInDyn | | |
| E7 | Move on a slave, commands not allowed | | |
| F1 | 0x4002 on the first start | | |
| G1 | Unlinked torque limit | | |

## Compile fixes

One unified diff per template or test-program fix (B1, B2).

## Problems with the protocol

Menu names that differ, steps that did not work, checks that are missing.
