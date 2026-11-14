# Project fixtures

TwinCAT projects from public repositories, trimmed down to what `axis_xti.py lint` reads at
project level. Each folder holds one project and its upstream licence (`LICENSE`). They are
public sample and demo projects; none comes from a customer machine.

| Folder | Upstream (commit) | Licence |
|---|---|---|
| `geardemo` | [Beckhoff-JP/GearDemo](https://github.com/Beckhoff-JP/GearDemo) (`8cf25df`), `FOOM2022_CompactMotorDemo.tsproj` | MIT |
| `amr_demo` | [Beckhoff-USA-Community/AMR_Demo](https://github.com/Beckhoff-USA-Community/AMR_Demo) (`06cd17c`), `AMR_Demo/` | 0BSD |
| `i950_dual_axis` | [milanlazov/twincat-dual-axis-coordinator](https://github.com/milanlazov/twincat-dual-axis-coordinator) (`f58f356`), `src/ComissioningExample/` | MIT |
| `triamec_ethercat` | [Triamec/NcEtherCat](https://github.com/Triamec/NcEtherCat) (`997e915`), `NCEtherCAT/` | Unlicense |
| `triamec_trialink` | [Triamec/NcTriaLink](https://github.com/Triamec/NcTriaLink) (`5e7f526`), `NCTriaLink/` | Unlicense |
| `xts_open` | [chris-k84/Xts_Library](https://github.com/chris-k84/Xts_Library) (`661f4ec`), `XtsOpenProject/` | MIT |

## How they were trimmed

File names, folder layout, element names and values are as upstream; content was removed,
never added or changed:

- `.tsproj`: kept `Project/Motion` (`NC`, `MC` reference), `Project/Io` and `Mappings`;
  removed `System`, `Plc` and the project's target attributes.
- Everywhere: removed `DataTypes`, and under the NC the `Vars` and `Image` process-image
  layouts. Removed the `AmsNetId` and `BIC` (serial number) attributes.
- I/O devices and boxes: kept `Name`, child boxes and `EtherCAT/Pdo` (with entries);
  removed address information, slave settings and init commands. In `amr_demo` and
  `xts_open` the PDOs of boxes no axis is linked to were removed as well.
- Other `_Config` files: kept only `Mappings` and `UnrestoredVarLinks`; files with neither
  were dropped (PLC sources and TcCOM settings are not here).
- `amr_demo`: the files of `Device 2 (EtherCAT)`, which the project does not reference,
  were dropped. `xts_open`: the mover axis's embedded TcCOM `Module` and
  `_Config/NC/Channels` were dropped.

## What each one is for

- `geardemo`: clean. Two CiA 402 axes on EL7201 terminals, NC and I/O inline in the
  `.tsproj`, every drive, encoder and PLC link in place: no project findings.
- `amr_demo`: NC.xti, axis files, I/O files and the PLC instance in separate files. The
  drive links live in the axis files with an empty owner. Leftover unrestored links to an
  axis `Lift` the NC no longer has (L5, info). Base for the edited copies in the tests.
- `i950_dual_axis`: two drives whose PDO assignment sends positive and negative torque
  limit and upper and lower speed limit, with nothing linked to them (L6).
- `triamec_ethercat`: one two-channel drive for two axes; link names put the channel in
  front (`Axis 0^MainOutputs^Control Word`), which must still count as linked.
- `triamec_trialink`: drive and encoder linked to PLC variables instead of I/O: linked.
- `xts_open`: an XTS mover whose drive and encoder are connected to a TcCOM object
  (`LinkedTo`) with no links at all: linked.
