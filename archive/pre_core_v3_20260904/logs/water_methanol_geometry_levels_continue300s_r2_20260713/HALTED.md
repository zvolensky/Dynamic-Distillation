# Run Halted on Dynamic Instability

This continuation was deliberately stopped at 270 s of continuation time
(570 s cumulative source time). The steady-state score peaked at 1124.674.

The dominant rate was the stage-7 Water vapor inventory (`tray_V`), with a
maximum relative state rate above 3.37/s. Vessel levels, pressure, and
temperature remained finite, so the evidence identifies a vapor-state dynamic
failure rather than vessel overflow or pressure collapse.

At the final logged point:

- top level: 49.43%
- bottom level: 53.39%
- distillate flow: 5,506.50 lbmol/h
- bottoms controller output: 15,922.15 lbmol/h
- top pressure: 14.70 psia
- top-drum pressure: 14.62 psia
- condenser duty: -373.11 MMBtu/h
- reboiler duty: 368.68 MMBtu/h
- distillate Methanol: 91.45 mol%
- bottoms Water: 89.53 mol%

The source checkpoint at 300 s remains the last accepted restart point. No
checkpoint was exported from this unstable continuation.
