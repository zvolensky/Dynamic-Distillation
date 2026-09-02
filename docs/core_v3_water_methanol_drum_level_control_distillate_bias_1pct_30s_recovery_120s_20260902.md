# Water-methanol top-drum level-control run

- Result: `drum_level_control_hold_passed`
- Controller: `Kc=42.0, Ti=365.0 s`
- Feed multiplier: `1.0`
- Distillate bias: `1.01` through `30.0 s`; removed: `True`
- Distillate: `7936.640000` to `7926.059598 lbmol/h`
- Drum level: `50.245722%` to `50.243681%`
- Clock/sim ratio: `5.617525`
- Feed disturbance removed: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 120.000 s
Qc: -364260934.215455 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7926.059598 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547717 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7936.640000 lbmol/h, T=215.599159 F, P=17.645285 psia, h=-119924.098155 BTU/lbmol, x(Water)=0.98336482, x(Methanol)=0.01663518
Distillate drum level: 50.243681%
Bottom drum level: 51.746555%
Steady-state score: 0.066655422 (steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.111798 | 6.108106 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636473 | 15.110924 | 123.674712 | 1.339359 | 15819.320571 | 23809.939998 | 0.03998069 | 0.96001931 | 0.01663518 | 0.98336482
3 | rectifying_volume_2 | tray | 152.852466 | 15.508569 | 125.321156 | 1.371406 | 15719.034102 | 23755.960567 | 0.07700067 | 0.92299933 | 0.03218118 | 0.96781882
4 | rectifying_volume_3 | tray | 155.617098 | 15.891126 | 128.051916 | 1.401451 | 15549.564540 | 23655.674098 | 0.13512643 | 0.86487357 | 0.05674764 | 0.94325236
5 | rectifying_volume_4 | tray | 159.294546 | 16.255609 | 132.622192 | 1.428730 | 15283.070204 | 23486.204537 | 0.22486291 | 0.77513709 | 0.09508495 | 0.90491505
6 | rectifying_volume_5 | tray | 164.435334 | 16.597706 | 140.319339 | 1.451903 | 14900.952511 | 23219.710202 | 0.35819912 | 0.64180088 | 0.15368939 | 0.84631061
7 | rectifying_volume_6 | tray | 171.698151 | 16.912395 | 152.715196 | 1.468757 | 14439.449429 | 22837.592511 | 0.53637408 | 0.46362592 | 0.23949703 | 0.76050297
8 | feed_tray | feed_tray | 181.085248 | 17.215822 | 209.450012 | 1.435583 | 29601.882802 | 22376.089431 | 0.71591354 | 0.28408646 | 0.35202639 | 0.64797361
9 | stripping_tray | tray | 200.169885 | 17.467402 | 233.970412 | 1.423235 | 29091.847473 | 21665.242806 | 0.91349579 | 0.08650421 | 0.61793797 | 0.38206203
10 | combined_reboiler_sump | reboiler_sump | 215.599159 | 17.645285 | 3081.516258 | 3.524080 | 7936.640000 | 21155.207479 | 0.98336482 | 0.01663518 | 0.88728355 | 0.11271645
```
