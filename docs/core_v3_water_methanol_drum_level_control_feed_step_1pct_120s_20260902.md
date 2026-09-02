# Water-methanol top-drum level-control run

- Result: `drum_level_control_feed_step_passed`
- Controller: `Kc=42.0, Ti=365.0 s`
- Feed multiplier: `1.01`
- Distillate: `7936.640000` to `7938.227002 lbmol/h`
- Drum level: `50.245722%` to `50.246149%`
- Clock/sim ratio: `10.483376`
- Feed disturbance removed: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 120.000 s
Qc: -364306640.136503 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7938.227002 lbmol/h, T=148.738509 F, P=14.700000 psia, h=-101176.547355 BTU/lbmol, x(Water)=0.01663517, x(Methanol)=0.98336483
Bottoms: F=7936.640000 lbmol/h, T=215.528441 F, P=17.648399 psia, h=-119919.703611 BTU/lbmol, x(Water)=0.98309222, x(Methanol)=0.01690778
Distillate drum level: 50.246149%
Bottom drum level: 51.846077%
Steady-state score: 0.98020005 (steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738509 | 14.700000 | 3968.367604 | 6.107707 | 15873.300000 | - | 0.01663517 | 0.98336483 | 0.00689029 | 0.99310971
2 | rectifying_volume_1 | tray | 150.636633 | 15.111019 | 123.674613 | 1.339367 | 15819.390543 | 23812.947269 | 0.03997594 | 0.96002406 | 0.01663322 | 0.98336678
3 | rectifying_volume_2 | tray | 152.852238 | 15.508756 | 125.320419 | 1.371422 | 15719.375737 | 23759.009988 | 0.07697219 | 0.92302781 | 0.03216932 | 0.96783068
4 | rectifying_volume_3 | tray | 155.614665 | 15.891413 | 128.048399 | 1.401475 | 15550.790455 | 23658.890623 | 0.13501148 | 0.86498852 | 0.05669933 | 0.94330067
5 | rectifying_volume_4 | tray | 159.284399 | 16.256024 | 132.608315 | 1.428767 | 15286.790888 | 23489.956670 | 0.22448321 | 0.77551679 | 0.09492265 | 0.90507735
6 | rectifying_volume_5 | tray | 164.402394 | 16.598330 | 140.270708 | 1.451973 | 14910.582934 | 23224.910981 | 0.35713668 | 0.64286332 | 0.15321332 | 0.84678668
7 | rectifying_volume_6 | tray | 171.608697 | 16.913402 | 152.574562 | 1.468929 | 14459.329893 | 22845.946043 | 0.53404637 | 0.46595363 | 0.23828130 | 0.76171870
8 | feed_tray | feed_tray | 180.901219 | 17.217645 | 209.525916 | 1.435528 | 29793.629770 | 22388.959764 | 0.71268090 | 0.28731910 | 0.34952096 | 0.65047904
9 | stripping_tray | tray | 199.893650 | 17.470290 | 234.164339 | 1.423617 | 29275.508226 | 21683.546091 | 0.91166083 | 0.08833917 | 0.61335730 | 0.38664270
10 | combined_reboiler_sump | reboiler_sump | 215.528441 | 17.648399 | 3086.686397 | 3.520320 | 7936.640000 | 21159.577271 | 0.98309222 | 0.01690778 | 0.88567749 | 0.11432251
```
