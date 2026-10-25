---
name: twincat-motion
description: "Use for Beckhoff TwinCAT 3 motion control: NC axis configuration and parameters, Tc2_MC2 / PLCopen MC_ function blocks (MC_Power, MC_Home, MC_MoveAbsolute, MC_Reset), homing, gearing and cam coupling, axis errors and why an axis will not enable or move. Not for the CiA 402 drive state machine on its own (use cia402-motion), EtherCAT network faults (use ethercat-diagnostics), or general Structured Text (use twincat-st). DRAFT: under development."
---

# twincat-motion

> **Draft.** This skill is under development and not ready to install.
>
> **Reference material only. Not for safety functions.** Motion configuration must be
> reviewed and validated by a qualified engineer before it runs on a machine.

## Goal

Get a TwinCAT NC axis configured, enabled, homed and moving correctly, and diagnose why it
is not.
