# Water-methanol dual level-control feed disturbance

- Result: `dual_level_control_feed_step_passed`
- Feed multiplier: `1.05`
- Duration: `1.0 s`
- Distillate: `7936.640000` to `7936.634142 lbmol/h`
- Bottoms: `7936.640000` to `7936.672142 lbmol/h`
- Drum level: `50.245722%` to `50.245720%`
- Bottom level: `51.746555%` to `51.746572%`
- Clock/sim ratio: `91.186078`
- Feed disturbance removed: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 1.000 s
Qc: -364246431.137223 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7936.634142 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547704 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7936.672142 lbmol/h, T=215.599025 F, P=17.645245 psia, h=-119924.100045 BTU/lbmol, x(Water)=0.98336476, x(Methanol)=0.01663524
Distillate drum level: 50.245720%
Bottom drum level: 51.746572%
Steady-state score: 4.7617471 (not steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.323151 | 6.107776 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636384 | 15.110895 | 123.674693 | 1.339357 | 15819.310552 | 23809.011279 | 0.03998066 | 0.96001934 | 0.01663517 | 0.98336483
3 | rectifying_volume_2 | tray | 152.852287 | 15.508509 | 125.321115 | 1.371402 | 15719.013254 | 23754.932302 | 0.07700063 | 0.92299937 | 0.03218114 | 0.96781886
4 | rectifying_volume_3 | tray | 155.616819 | 15.891031 | 128.051852 | 1.401443 | 15549.532572 | 23654.450834 | 0.13512637 | 0.86487363 | 0.05674756 | 0.94325244
5 | rectifying_volume_4 | tray | 159.294151 | 16.255474 | 132.622103 | 1.428719 | 15283.026912 | 23484.693458 | 0.22486281 | 0.77513719 | 0.09508480 | 0.90491520
6 | rectifying_volume_5 | tray | 164.434801 | 16.597521 | 140.319221 | 1.451888 | 14900.900771 | 23217.823161 | 0.35819887 | 0.64180113 | 0.15368908 | 0.84631092
7 | rectifying_volume_6 | tray | 171.697255 | 16.912155 | 152.715141 | 1.468737 | 14439.573105 | 22835.263006 | 0.53636866 | 0.46363134 | 0.23949386 | 0.76050614
8 | feed_tray | feed_tray | 181.071940 | 17.215662 | 209.652010 | 1.435349 | 29698.329137 | 22373.892710 | 0.71569497 | 0.28430503 | 0.35185567 | 0.64814433
9 | stripping_tray | tray | 200.166535 | 17.467332 | 233.988691 | 1.423217 | 29100.279141 | 21668.945890 | 0.91347563 | 0.08652437 | 0.61788706 | 0.38211294
10 | combined_reboiler_sump | reboiler_sump | 215.599025 | 17.645245 | 3081.517328 | 3.524072 | 7936.672142 | 21156.957687 | 0.98336476 | 0.01663524 | 0.88728320 | 0.11271680
```
