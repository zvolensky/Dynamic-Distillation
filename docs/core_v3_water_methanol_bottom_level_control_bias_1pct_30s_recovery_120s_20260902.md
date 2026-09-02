# Water-methanol bottom-sump level-control run

- Result: `bottom_level_control_bias_recovery_passed`
- Controller: `Kc=24.0, Ti=365.0 s`
- Bottoms bias: `1.01` through `30.0 s`; removed: `True`
- Bottoms: `7936.640000` to `7926.068422 lbmol/h`
- Bottom level: `51.746555%` to `51.742980%`
- Clock/sim ratio: `12.350740`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 120.000 s
Qc: -364260843.674236 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7936.640000 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547669 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7926.068422 lbmol/h, T=215.599159 F, P=17.645287 psia, h=-119924.097605 BTU/lbmol, x(Water)=0.98336479, x(Methanol)=0.01663521
Distillate drum level: 50.245720%
Bottom drum level: 51.742980%
Steady-state score: 0.066599834 (steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.323117 | 6.107776 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636474 | 15.110924 | 123.674712 | 1.339360 | 15819.320540 | 23809.950548 | 0.03998067 | 0.96001933 | 0.01663518 | 0.98336482
3 | rectifying_volume_2 | tray | 152.852467 | 15.508569 | 125.321154 | 1.371407 | 15719.033985 | 23755.971131 | 0.07700064 | 0.92299936 | 0.03218116 | 0.96781884
4 | rectifying_volume_3 | tray | 155.617099 | 15.891127 | 128.051911 | 1.401451 | 15549.564281 | 23655.684682 | 0.13512635 | 0.86487365 | 0.05674761 | 0.94325239
5 | rectifying_volume_4 | tray | 159.294545 | 16.255610 | 132.622183 | 1.428730 | 15283.069713 | 23486.215153 | 0.22486278 | 0.77513722 | 0.09508489 | 0.90491511
6 | rectifying_volume_5 | tray | 164.435332 | 16.597707 | 140.319320 | 1.451903 | 14900.951478 | 23219.720847 | 0.35819890 | 0.64180110 | 0.15368930 | 0.84631070
7 | rectifying_volume_6 | tray | 171.698146 | 16.912396 | 152.715167 | 1.468757 | 14439.447122 | 22837.603081 | 0.53637383 | 0.46362617 | 0.23949690 | 0.76050310
8 | feed_tray | feed_tray | 181.085245 | 17.215824 | 209.449986 | 1.435583 | 29601.879119 | 22376.099613 | 0.71591339 | 0.28408661 | 0.35202627 | 0.64797373
9 | stripping_tray | tray | 200.169881 | 17.467404 | 233.970391 | 1.423235 | 29091.842949 | 21665.252714 | 0.91349572 | 0.08650428 | 0.61793780 | 0.38206220
10 | combined_reboiler_sump | reboiler_sump | 215.599159 | 17.645287 | 3081.303284 | 3.524253 | 7926.068422 | 21155.216834 | 0.98336479 | 0.01663521 | 0.88728340 | 0.11271660
```
