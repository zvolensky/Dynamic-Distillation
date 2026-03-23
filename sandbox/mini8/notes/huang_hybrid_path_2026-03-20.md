# Huang Hybrid Path

Date: 2026-03-20

Purpose:
- Make it explicit that the repo is now applying a Huang-inspired hybrid step as the next practical path after the dense simultaneous mini8 pilot proved too expensive.

Why Huang here:
- Huang's GRU work uses a partitioned dynamic strategy instead of one giant simultaneous solve.
- The useful near-term idea is the Hydraulic Time Constant (HTC) approach for tray liquid dynamics.
- That fits the current codebase much better than a full Wittgens-style tray/downcomer implicit DAE rebuild.

What is applied now:
- In `src/dynamic_distillation/uv_flash_sandbox_v1.py`, the mini8 sequential UV sandbox now supports `--liquid-flow-mode huang-htc`.
- In this mode, tray liquid outflow is computed from:
  - tray liquid holdup
  - divided by a hydraulic time constant
- The hydraulic time constant is read from:
  - `Huang Liquid HTC (sec)` if present
  - otherwise `Hydraulic Time Constant (sec)` if present
  - otherwise the Excel `Stage time constant [tau] (sec)`
  - otherwise the column `tau_eq_sec` fallback

What is not applied yet:
- The full Huang pressure update sequence in the larger column model:
  - solve mass/energy/VLE at assumed tray pressure
  - then update pressure from vapor-phase mass balance
  - then update tray pressure drops from instantaneous liquid-vapor traffic
- The current mini8 UV sandbox still uses its existing partitioned pressure/vapor treatment.

Interpretation:
- This is a practical bridge, not a claim that the full Huang architecture has already been implemented.
- The intent is to test whether Huang-style liquid dynamics improve stability and operating-point holding before investing in a larger pressure-side rewrite.

Immediate next checks:
- Compare mini8 short transients for:
  - `francis + conductance`
  - `huang-htc + conductance`
- Judge on:
  - tray temperature drift
  - drum/sump holdup drift
  - pressure smoothness
  - whether open-loop drift is reduced
