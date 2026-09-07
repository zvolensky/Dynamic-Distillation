# Water-methanol dual level-control feed disturbance

- Result: `dual_level_control_feed_step_passed`
- Feed multiplier: `1.05`
- Duration: `600.0 s`
- Distillate: `7936.640000` to `7966.688051 lbmol/h`
- Bottoms: `7936.640000` to `9037.360362 lbmol/h`
- Drum level: `50.245722%` to `50.249796%`
- Bottom level: `51.746555%` to `51.874237%`
- Clock/sim ratio: `10.134423`
- Feed disturbance removed: `True`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 600.000 s
Qc: -364507510.079534 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7966.688051 lbmol/h, T=148.731441 F, P=14.700000 psia, h=-101171.235881 BTU/lbmol, x(Water)=0.01637253, x(Methanol)=0.98362747
Bottoms: F=9037.360362 lbmol/h, T=213.634770 F, P=17.693565 psia, h=-119804.585046 BTU/lbmol, x(Water)=0.97589675, x(Methanol)=0.02410325
Distillate drum level: 50.249796%
Bottom drum level: 51.874237%
Steady-state score: 2.0225928 (not steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.731441 | 14.700000 | 3968.098886 | 6.107209 | 15873.300000 | - | 0.01637253 | 0.98362747 | 0.00678149 | 0.99321851
2 | rectifying_volume_1 | tray | 150.578131 | 15.111716 | 123.576264 | 1.339480 | 15827.231984 | 23830.629894 | 0.03774772 | 0.96225228 | 0.01570581 | 0.98429419
3 | rectifying_volume_2 | tray | 152.702670 | 15.510547 | 125.070624 | 1.371707 | 15741.284642 | 23783.662925 | 0.07137276 | 0.92862724 | 0.02982702 | 0.97017298
4 | rectifying_volume_3 | tray | 155.301454 | 15.894972 | 127.516117 | 1.402065 | 15596.699750 | 23695.659414 | 0.12361953 | 0.87638047 | 0.05190101 | 0.94809899
5 | rectifying_volume_4 | tray | 158.678314 | 16.262461 | 131.535979 | 1.429919 | 15370.477344 | 23547.097455 | 0.20345245 | 0.79654755 | 0.08593881 | 0.91406119
6 | rectifying_volume_5 | tray | 163.288690 | 16.609317 | 138.179948 | 1.454181 | 15044.732389 | 23313.711042 | 0.32161015 | 0.67838985 | 0.13741644 | 0.86258356
7 | rectifying_volume_6 | tray | 169.712870 | 16.931017 | 148.885550 | 1.473068 | 14636.493523 | 22975.637873 | 0.48316510 | 0.51683490 | 0.21254305 | 0.78745695
8 | feed_tray | feed_tray | 178.240444 | 17.244403 | 205.933385 | 1.439153 | 30698.975908 | 22548.085339 | 0.66223305 | 0.33776695 | 0.31349785 | 0.68650215
9 | stripping_tray | tray | 195.571084 | 17.510414 | 231.389873 | 1.433705 | 30018.139351 | 21919.659249 | 0.87945356 | 0.12054644 | 0.54421697 | 0.45578303
10 | combined_reboiler_sump | reboiler_sump | 213.634770 | 17.693565 | 3068.574500 | 3.538795 | 9037.360362 | 21215.297360 | 0.97589675 | 0.02410325 | 0.84557298 | 0.15442702
```
