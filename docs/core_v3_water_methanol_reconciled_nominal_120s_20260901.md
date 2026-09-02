# Reconciled water-methanol nominal dynamic hold

- Result: `reconciled_nominal_hold_passed`
- Simulated: `120.0 s` at `0.5 s` per step
- Wall clock: `270.722760 s`
- Clock/sim ratio: `2.256023`
- Component conservation error: `7.696806e-14 lbmol`
- Energy conservation error: `1.192093e-08 BTU`
- Feed disturbance active: `False`
- Component-specific logic: `False`

```text
END-OF-RUN OPERATING SUMMARY
Time: 120.000 s
Qc: -365357167.433259 BTU/h
Qr: 370687233.701380 BTU/h
Distillate: F=7936.640000 lbmol/h, T=149.122827 F, P=14.700000 psia, h=-101464.543146 BTU/lbmol, x(Water)=0.03087193, x(Methanol)=0.96912807
Bottoms: F=7936.640000 lbmol/h, T=211.262984 F, P=17.671024 psia, h=-119710.419387 BTU/lbmol, x(Water)=0.96912807, x(Methanol)=0.03087193
Distillate drum level: 49.908319%
Bottom drum level: 52.388616%
Steady-state score: 0 (steady; criterion <= 1.0)

FINAL TRAY PROFILES
Stage | Volume | Type | T_F | P_psia | ML_lbmol | MV_lbmol | Lout_lbmolph | Vout_lbmolph | x_Water | x_Methanol | y_Water | y_Methanol
1 | reflux_drum | reflux_drum | 149.122827 | 14.700000 | 3968.323333 | 6.157300 | 15873.300000 | - | 0.03087193 | 0.96912807 | 0.01278933 | 0.98721067
2 | rectifying_volume_1 | tray | 151.656802 | 15.138380 | 125.339427 | 1.340584 | 15755.402721 | 23809.940000 | 0.07413878 | 0.92586122 | 0.03087193 | 0.96912807
3 | rectifying_volume_2 | tray | 154.838789 | 15.557764 | 128.559020 | 1.373484 | 15555.656743 | 23692.042721 | 0.14242191 | 0.85757809 | 0.05964474 | 0.94035526
4 | rectifying_volume_3 | tray | 159.111115 | 15.954447 | 134.026961 | 1.402973 | 15243.775621 | 23492.296743 | 0.24793266 | 0.75206734 | 0.10473586 | 0.89526414
5 | rectifying_volume_4 | tray | 165.129186 | 16.323205 | 143.331826 | 1.427359 | 14809.634383 | 23180.415621 | 0.40277363 | 0.59722637 | 0.17361420 | 0.82638580
6 | rectifying_volume_5 | tray | 173.549744 | 16.658577 | 157.879306 | 1.443979 | 14328.353243 | 22746.274383 | 0.59813901 | 0.40186099 | 0.27300953 | 0.72699047
7 | rectifying_volume_6 | tray | 183.658043 | 16.959415 | 173.895450 | 1.451863 | 13988.542134 | 22264.993243 | 0.76745716 | 0.23254284 | 0.39592945 | 0.60407055
8 | feed_tray | feed_tray | 191.937811 | 17.252299 | 225.952324 | 1.421178 | 29208.662982 | 21925.182134 | 0.85416161 | 0.14583839 | 0.50082258 | 0.49917742
9 | stripping_tray | tray | 211.262984 | 17.488737 | 242.628571 | 1.402182 | 29265.137209 | 21272.022982 | 0.96912807 | 0.03087193 | 0.81126737 | 0.18873263
10 | combined_reboiler_sump | reboiler_sump | 211.262984 | 17.671024 | 3081.516258 | 3.521635 | 7936.640000 | 21328.497209 | 0.96912807 | 0.03087193 | 0.96912807 | 0.03087193
```
