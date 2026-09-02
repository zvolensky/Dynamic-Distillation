# Water-methanol bottom-sump level-control run

- Result: `bottom_level_control_bias_recovery_passed`
- Controller: `Kc=24.0, Ti=365.0 s`
- Bottoms bias: `1.01` through `1.0 s`; removed: `True`
- Bottoms: `7936.640000` to `7935.941839 lbmol/h`
- Bottom level: `51.746555%` to `51.746190%`
- Clock/sim ratio: `68.905074`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 2.000 s
Qc: -364260619.392912 BTU/h
Qr: 370180573.116055 BTU/h
Distillate: F=7936.640000 lbmol/h, T=148.738510 F, P=14.700000 psia, h=-101176.547704 BTU/lbmol, x(Water)=0.01663518, x(Methanol)=0.98336482
Bottoms: F=7935.941839 lbmol/h, T=215.599156 F, P=17.645284 psia, h=-119924.098231 BTU/lbmol, x(Water)=0.98336482, x(Methanol)=0.01663518
Distillate drum level: 50.245722%
Bottom drum level: 51.746190%
Steady-state score: 0.0043983382 (not steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 148.738510 | 14.700000 | 3968.323332 | 6.107776 | 15873.300000 | - | 0.01663518 | 0.98336482 | 0.00689030 | 0.99310970
2 | rectifying_volume_1 | tray | 150.636473 | 15.110924 | 123.674712 | 1.339359 | 15819.320530 | 23809.935910 | 0.03998068 | 0.96001932 | 0.01663518 | 0.98336482
3 | rectifying_volume_2 | tray | 152.852465 | 15.508569 | 125.321156 | 1.371406 | 15719.034017 | 23755.956345 | 0.07700067 | 0.92299933 | 0.03218117 | 0.96781883
4 | rectifying_volume_3 | tray | 155.617097 | 15.891126 | 128.051916 | 1.401451 | 15549.564419 | 23655.669635 | 0.13512642 | 0.86487358 | 0.05674764 | 0.94325236
5 | rectifying_volume_4 | tray | 159.294544 | 16.255609 | 132.622192 | 1.428730 | 15283.070054 | 23486.199775 | 0.22486291 | 0.77513709 | 0.09508495 | 0.90491505
6 | rectifying_volume_5 | tray | 164.435332 | 16.597705 | 140.319338 | 1.451903 | 14900.952345 | 23219.705142 | 0.35819912 | 0.64180088 | 0.15368939 | 0.84631061
7 | rectifying_volume_6 | tray | 171.698148 | 16.912394 | 152.715195 | 1.468757 | 14439.449259 | 22837.587222 | 0.53637408 | 0.46362592 | 0.23949702 | 0.76050298
8 | feed_tray | feed_tray | 181.085245 | 17.215822 | 209.450012 | 1.435583 | 29601.882644 | 22376.084045 | 0.71591353 | 0.28408647 | 0.35202638 | 0.64797362
9 | stripping_tray | tray | 200.169881 | 17.467401 | 233.970412 | 1.423235 | 29091.847274 | 21665.237527 | 0.91349578 | 0.08650422 | 0.61793795 | 0.38206205
10 | combined_reboiler_sump | reboiler_sump | 215.599156 | 17.645284 | 3081.494541 | 3.524098 | 7935.941839 | 21155.202422 | 0.98336482 | 0.01663518 | 0.88728355 | 0.11271645
```
