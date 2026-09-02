# Reconciled water-methanol dynamic feed-step run

- Result: `open_loop_feed_step_passed`
- Simulated: `10.0 s` at `0.5 s` per step
- Wall clock: `176.601868 s`
- Clock/sim ratio: `17.660187`
- Component conservation error: `3.338996e-13 lbmol`
- Energy conservation error: `7.243216e-08 BTU`
- Feed multiplier during run: `1.01`
- Feed disturbance removed after run: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 10.000 s
Qc: -364246567.478927 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7936.640000 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547690 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7936.640000 lbmol/h, T=215.598690 F, P=17.645471 psia, h=-119924.032445 BTU/lbmol, x(Water)=0.98336135, x(Methanol)=0.01663865
Distillate drum level: 50.245703%
Bottom drum level: 51.747998%
Steady-state score: 0.99009901 (not steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.321424 | 6.107779 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636379 | 15.110895 | 123.674705 | 1.339357 | 15819.319755 | 23809.020582 | 0.03998046 | 0.96001954 | 0.01663509 | 0.98336491
3 | rectifying_volume_2 | tray | 152.852288 | 15.508513 | 125.321138 | 1.371402 | 15719.029944 | 23755.044777 | 0.07700029 | 0.92299971 | 0.03218100 | 0.96781900
4 | rectifying_volume_3 | tray | 155.616842 | 15.891044 | 128.051884 | 1.401444 | 15549.558305 | 23654.765288 | 0.13512583 | 0.86487417 | 0.05674734 | 0.94325266
5 | rectifying_volume_4 | tray | 159.294208 | 16.255504 | 132.622151 | 1.428722 | 15283.072442 | 23485.307653 | 0.22486178 | 0.77513822 | 0.09508438 | 0.90491562
6 | rectifying_volume_5 | tray | 164.434781 | 16.597579 | 140.319309 | 1.451892 | 14901.083993 | 23218.839747 | 0.35819325 | 0.64180675 | 0.15368662 | 0.84631338
7 | rectifying_volume_6 | tray | 171.695430 | 16.912258 | 152.714971 | 1.468744 | 14441.104547 | 22836.869377 | 0.53631532 | 0.46368468 | 0.23946607 | 0.76053393
8 | feed_tray | feed_tray | 181.062867 | 17.215866 | 209.689601 | 1.435320 | 29722.414424 | 22376.428800 | 0.71553074 | 0.28446926 | 0.35172799 | 0.64827201
9 | stripping_tray | tray | 200.143707 | 17.467598 | 234.098859 | 1.423169 | 29152.914105 | 21667.288545 | 0.91332441 | 0.08667559 | 0.61750658 | 0.38249342
10 | combined_reboiler_sump | reboiler_sump | 215.598690 | 17.645471 | 3081.591810 | 3.524051 | 7936.640000 | 21154.587910 | 0.98336135 | 0.01663865 | 0.88726320 | 0.11273680
```
