# Water-methanol top-drum level-control run

- Result: `drum_level_control_feed_step_passed`
- Controller: `Kc=42.0, Ti=365.0 s`
- Feed multiplier: `1.01`
- Distillate: `7936.640000` to `7936.639656 lbmol/h`
- Drum level: `50.245722%` to `50.245722%`
- Clock/sim ratio: `219.872600`
- Feed disturbance removed: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 0.500 s
Qc: -364259496.743675 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7936.639656 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547704 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7936.640000 lbmol/h, T=215.599146 F, P=17.645281 psia, h=-119924.098417 BTU/lbmol, x(Water)=0.98336482, x(Methanol)=0.01663518
Distillate drum level: 50.245722%
Bottom drum level: 51.746555%
Steady-state score: 0.99010116 (not steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.323323 | 6.107776 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636466 | 15.110921 | 123.674711 | 1.339359 | 15819.319702 | 23809.862747 | 0.03998068 | 0.96001932 | 0.01663518 | 0.98336482
3 | rectifying_volume_2 | tray | 152.852451 | 15.508564 | 125.321152 | 1.371406 | 15719.032250 | 23755.869014 | 0.07700067 | 0.92299933 | 0.03218117 | 0.96781883
4 | rectifying_volume_3 | tray | 155.617073 | 15.891117 | 128.051910 | 1.401450 | 15549.561540 | 23655.552689 | 0.13512642 | 0.86487358 | 0.05674763 | 0.94325237
5 | rectifying_volume_4 | tray | 159.294507 | 16.255596 | 132.622184 | 1.428729 | 15283.065810 | 23486.034245 | 0.22486291 | 0.77513709 | 0.09508493 | 0.90491507
6 | rectifying_volume_5 | tray | 164.435278 | 16.597686 | 140.319326 | 1.451901 | 14900.946556 | 23219.466239 | 0.35819910 | 0.64180090 | 0.15368936 | 0.84631064
7 | rectifying_volume_6 | tray | 171.698056 | 16.912367 | 152.715184 | 1.468754 | 14439.454210 | 22837.242395 | 0.53637371 | 0.46362629 | 0.23949680 | 0.76050320
8 | feed_tray | feed_tray | 181.083873 | 17.215797 | 209.470856 | 1.435558 | 29611.809085 | 22375.652417 | 0.71589138 | 0.28410862 | 0.35200906 | 0.64799094
9 | stripping_tray | tray | 200.169641 | 17.467391 | 233.971675 | 1.423233 | 29092.427523 | 21665.888450 | 0.91349443 | 0.08650557 | 0.61793452 | 0.38206548
10 | combined_reboiler_sump | reboiler_sump | 215.599146 | 17.645281 | 3081.516286 | 3.524080 | 7936.640000 | 21155.588139 | 0.98336482 | 0.01663518 | 0.88728353 | 0.11271647
```
