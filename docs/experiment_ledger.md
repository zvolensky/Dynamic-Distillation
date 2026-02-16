# Experiment Ledger

Updated: 2026-02-15 20:39:50 (local)

This file is auto-generated from `logs/column_summary_*.csv`, `logs/feasibility_trim_search_*.csv`, and `logs/run_registry.csv`.

Total runs indexed: **343**  
Runs with known CLI command: **31**  
Runs with unknown CLI command: **312**

Primary searchable source: `docs/experiment_ledger.csv`.

Duplicate indicators in CSV: `exact_command_dup_group`, `exact_command_dup_count`, `suspected_dup_group`, `suspected_dup_count`, `suspected_duplicate`.

## Duplicate Signals

Exact-command duplicate groups: **4** (rows in groups: **8**)  
Suspected-result duplicate groups: **31** (rows in groups: **78**)

### Exact Command Duplicates (Top 20)

| Group | Count | Run IDs |
|---|---:|---|
| `CMDDUP001` | 2 | `20260215_185348`, `20260215_174906` |
| `CMDDUP002` | 2 | `20260215_170604`, `20260215_160316` |
| `CMDDUP003` | 2 | `20260215_162944`, `20260215_144747` |
| `CMDDUP004` | 2 | `20260214_205627`, `20260214_150239` |

### Suspected Result Duplicates (Top 30)

| Group | Count | Run IDs |
|---|---:|---|
| `SIGDUP001` | 4 | `20260215_185348`, `20260215_174906`, `20260215_170604`, `20260215_160316` |
| `SIGDUP002` | 2 | `20260215_162944`, `20260215_144747` |
| `SIGDUP003` | 2 | `20260215_121942`, `20260215_073241` |
| `SIGDUP004` | 2 | `20260215_090609`, `20260215_083445` |
| `SIGDUP005` | 2 | `20260215_071617`, `20260215_070444` |
| `SIGDUP006` | 2 | `20260213_182007`, `20260213_181509` |
| `SIGDUP007` | 2 | `20260213_120416`, `20260213_115343` |
| `SIGDUP008` | 2 | `20260213_100128`, `20260213_095423` |
| `SIGDUP009` | 2 | `20260212_181918`, `20260212_170629` |
| `SIGDUP010` | 2 | `20260212_170232`, `20260212_170144` |
| `SIGDUP011` | 2 | `20260211_163158`, `20260210_203220` |
| `SIGDUP012` | 2 | `20260211_133239`, `20260211_131139` |
| `SIGDUP013` | 2 | `20260211_132338`, `20260211_131717` |
| `SIGDUP014` | 2 | `20260211_132015`, `20260211_131422` |
| `SIGDUP015` | 2 | `20260211_120935`, `20260211_120515` |
| `SIGDUP016` | 2 | `20260210_153246`, `20260210_150923` |
| `SIGDUP017` | 2 | `20260210_122915`, `20260210_122641` |
| `SIGDUP018` | 4 | `20260209_163210`, `20260209_162349`, `20260209_161327`, `20260209_093725` |
| `SIGDUP019` | 2 | `20260209_150210`, `20260209_131146` |
| `SIGDUP020` | 2 | `20260208_112403`, `20260208_091635` |
| `SIGDUP021` | 3 | `20260208_112315`, `20260207_155904`, `20260207_150105` |
| `SIGDUP022` | 2 | `20260208_081246`, `20260207_211337` |
| `SIGDUP023` | 2 | `20260207_181205`, `20260207_173727` |
| `SIGDUP024` | 3 | `20260207_170937`, `20260207_165752`, `20260207_160850` |
| `SIGDUP025` | 7 | `20260207_144502`, `20260207_143835`, `20260207_143632`, `20260207_125653`, `20260207_121951`, `20260207_090452`, `20260207_075336` |
| `SIGDUP026` | 2 | `20260207_101740`, `20260207_094400` |
| `SIGDUP027` | 6 | `20260206_165446`, `20260206_160324`, `20260206_123457`, `20260206_120741`, `20260206_114408`, `20260206_112234` |
| `SIGDUP028` | 2 | `20260206_105916`, `20260206_104352` |
| `SIGDUP029` | 3 | `20260206_094224`, `20260206_091504`, `20260205_222449` |
| `SIGDUP030` | 2 | `20260205_213628`, `20260205_211218` |

## Known CLI Commands

| Run ID | Date/Time | Source | Command | Final (P, xD, xB, R, Vb) |
|---|---|---|---|---|
| `20260215_200510` | 2026-02-15 20:05:10 | `auto-captured` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template_21_stage.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 3000 --dt 0.2 --log-every 100 --enable-level-control --enable-pressure-control --pressure-control-mv top-anchor --enable-distillate-composition-control --enable-bottoms-composition-control` | P=161.122; xD=; xB=; R=; Vb= |
| `20260215_185348` | 2026-02-15 18:53:48 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc=-3.0 --top-pressure-ti 60` | P=170.842; xD=0.100599; xB=0.161124; R=5952.48; Vb=11743.50 |
| `20260215_174906` | 2026-02-15 17:49:06 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc=-3.0 --top-pressure-ti 60` | P=170.842; xD=0.100599; xB=0.161124; R=5952.48; Vb=11743.50 |
| `20260215_170604` | 2026-02-15 17:06:04 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc -3.0 --top-pressure-ti 60` | P=170.842; xD=0.100599; xB=0.161124; R=5952.48; Vb=11743.50 |
| `20260215_162944` | 2026-02-15 16:29:44 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --no-equilibrium --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=221.227; xD=0.236757; xB=0.152549; R=4439.42; Vb=7807.51 |
| `20260215_160316` | 2026-02-15 16:03:16 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc -3.0 --top-pressure-ti 60` | P=170.842; xD=0.100599; xB=0.161124; R=5952.48; Vb=11743.50 |
| `20260215_144747` | 2026-02-15 14:47:47 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --no-equilibrium --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=221.227; xD=0.236757; xB=0.152549; R=4439.42; Vb=7807.51 |
| `20260215_135110` | 2026-02-15 13:51:10 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 1 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=230.868; xD=0.105845; xB=0.161138; R=5952.48; Vb=11743.50 |
| `20260215_125538` | 2026-02-15 12:55:38 | `auto-captured` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 2 --n-random 6 --seed 123 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=223.942; xD=0.094066; xB=0.157059; R=13854.55; Vb=10243.77 |
| `20260215_121942` | 2026-02-15 12:19:42 | `auto-captured` | `python tools/feasibility_trim_search.py --thermo stub --n-steps 1 --dt 0.2 --n-random 0 --xD-sp 0.05 --xB-sp 0.18 --show-top 1` | P=218.440; xD=0.050939; xB=0.166666; R=5952.48; Vb=11743.50 |
| `20260215_114500` | 2026-02-15 11:45:00 | `reconstructed-inferred` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --n-random 24 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002` | P=140.380; xD=0.090234; xB=0.166502; R=11853.78; Vb=14532.31 |
| `20260215_105634` | 2026-02-15 10:56:34 | `auto-captured` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --log-every 200 --reflux 2749.44 --boilup 28714.62 --enable-pressure-control --pressure-control-mv condenser-duty --condenser-duty-mode specified --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=226.549; xD=; xB=; R=; Vb= |
| `20260215_105542` | 2026-02-15 10:55:42 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --thermo-every 2 --n-random 0 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 1 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=219.319; xD=0.111417; xB=0.160999; R=5952.48; Vb=11743.50 |
| `20260215_094545` | 2026-02-15 09:45:45 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 300 --dt 0.2 --thermo-every 2 --n-random 2 --seed 42 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 3 --enforce-top-pressure --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc=-5e5 --top-pressure-ti 120` | P=216.512; xD=0.060084; xB=0.165308; R=5952.48; Vb=11743.50 |
| `20260215_091428` | 2026-02-15 09:14:28 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 400 --dt 0.2 --thermo-every 2 --n-random 3 --seed 42 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 4 --enforce-top-pressure --top-pressure-sp 220.44 --top-pressure-kc -1.0 --top-pressure-ti 60` | P=135.474; xD=0.069226; xB=0.164702; R=5952.48; Vb=11743.50 |
| `20260215_090609` | 2026-02-15 09:06:09 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 400 --dt 0.2 --thermo-every 2 --n-random 6 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7 --enforce-top-pressure --top-pressure-sp 220.44 --top-pressure-kc -1.0 --top-pressure-ti 60` | P=162.674; xD=0.065458; xB=0.166744; R=3203.96; Vb=14836.37 |
| `20260215_085820` | 2026-02-15 08:58:20 | `auto-captured` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --log-every 200 --reflux 11853.78 --boilup 14532.31` | P=140.380; xD=; xB=; R=; Vb= |
| `20260215_085803` | 2026-02-15 08:58:03 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 1200 --dt 0.2 --n-random 0 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 1 --enforce-top-pressure --top-pressure-sp 220.44 --top-pressure-kc -1.0 --top-pressure-ti 60` | P=184.004; xD=0.113799; xB=0.161443; R=5952.48; Vb=11743.50 |
| `20260215_084739` | 2026-02-15 08:47:39 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 300 --dt 0.2 --n-random 3 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002` | P=164.931; xD=0.058655; xB=0.165752; R=5952.48; Vb=11743.50 |
| `20260215_084643` | 2026-02-15 08:46:43 | `reconstructed-inferred` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 600 --dt 0.2 --n-random 8 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002` | P=180.824; xD=0.071418; xB=0.166766; R=3203.96; Vb=14836.37 |
| `20260215_083445` | 2026-02-15 08:34:45 | `reconstructed-session` | `python tools/feasibility_trim_search.py --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --include-energy --n-steps 400 --dt 0.2 --thermo-every 2 --n-random 6 --distillate-comp-component C4 --bottoms-comp-component C5 --tol-xd 0.002 --tol-xb 0.002 --show-top 7` | P=162.674; xD=0.065458; xB=0.166744; R=3203.96; Vb=14836.37 |
| `20260215_073349` | 2026-02-15 07:33:49 | `reconstructed-session` | `python tools/feasibility_trim_search.py --thermo table --thermo-table cache/thermo_table.json --n-steps 1 --dt 0.2 --n-random 1 --seed 2 --show-top 2` | P=163.465; xD=0.050939; xB=0.166659; R=5952.48; Vb=11743.50 |
| `20260215_073241` | 2026-02-15 07:32:41 | `reconstructed-session` | `python tools/feasibility_trim_search.py --thermo stub --n-steps 1 --dt 0.2 --n-random 2 --seed 1 --xD-sp 0.05 --xB-sp 0.18 --show-top 3` | P=218.440; xD=0.050939; xB=0.166666; R=5952.48; Vb=11743.50 |
| `20260215_071617` | 2026-02-15 07:16:17 | `auto-captured` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --n-steps 1 --thermo stub --log-every 1 --allow-repeat-command` | P=218.440; xD=; xB=; R=; Vb= |
| `20260215_070444` | 2026-02-15 07:04:44 | `auto-captured` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --n-steps 1 --thermo stub --log-every 1` | P=218.440; xD=; xB=; R=; Vb= |
| `20260214_215800` | 2026-02-14 21:58:00 | `exact-session` | `$env:PYTHONPATH='src'; python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --thermo-cache cache/thermo_cache.json --dt 0.2 --n-steps 6000 --log-every 50 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc -0.5 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-sp 0.0509385134 --distillate-comp-kc 500 --distillate-comp-ti 600 --reflux-cmd-min 2000 --reflux-cmd-max 10000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -500 --bottoms-comp-ti 600 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 15000` | P=233.076; xD=0.403354; xB=0.141329; R=2305.90; Vb=11769.47 |
| `20260214_214819` | 2026-02-14 21:48:19 | `exact-session` | `$env:PYTHONPATH='src'; python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --thermo-cache cache/thermo_cache.json --dt 0.2 --n-steps 1500 --log-every 25 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc -0.5 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-sp 0.0509385134 --distillate-comp-kc 500 --distillate-comp-ti 600 --reflux-cmd-min 2000 --reflux-cmd-max 10000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -500 --bottoms-comp-ti 600 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 15000` | P=237.554; xD=0.126920; xB=0.159907; R=5997.35; Vb=11747.72 |
| `20260214_205627` | 2026-02-14 20:56:27 | `exact-process-capture` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --dt 0.2 --n-steps 6000 --log-every 50 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc -150000 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-sp 0.0509385134 --distillate-comp-kc 500 --distillate-comp-ti 600 --reflux-cmd-min 2000 --reflux-cmd-max 10000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -500 --bottoms-comp-ti 600 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 15000` | P=175.759; xD=0.152800; xB=0.157903; R=6015.87; Vb=11749.27 |
| `20260214_203414` | 2026-02-14 20:34:14 | `exact-process-capture` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --dt 0.2 --n-steps 6000 --log-every 50 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv top-anchor --top-pressure-sp 220.44 --top-pressure-kc -0.5 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-component C4 --distillate-comp-sp 0.0509385134 --distillate-comp-kc 2000 --distillate-comp-ti 300 --reflux-cmd-min 2000 --reflux-cmd-max 12000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -1000 --bottoms-comp-ti 300 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 18000` | P=172.836; xD=0.358273; xB=0.143344; R=2776.02; Vb=11807.06 |
| `20260214_150239` | 2026-02-14 15:02:39 | `reconstructed-notes` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --dt 0.2 --n-steps 6000 --log-every 50 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc -150000 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-sp 0.0509385134 --distillate-comp-kc 500 --distillate-comp-ti 600 --reflux-cmd-min 2000 --reflux-cmd-max 10000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -500 --bottoms-comp-ti 600 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 15000` | P=226.677; xD=0.388611; xB=0.139502; R=2854.31; Vb=11770.92 |
| `20260214_145025` | 2026-02-14 14:50:25 | `reconstructed-notes` | `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo table --thermo-table cache/thermo_table.json --dt 0.2 --n-steps 1500 --log-every 50 --include-energy --condenser-pressure-drop-psi 2.0 --enable-level-control --top-level-sp 1388.9 --bottom-level-sp 794 --enable-pressure-control --pressure-control-mv condenser-duty --top-pressure-sp 220.44 --top-pressure-kc -150000 --top-pressure-ti 600 --enable-distillate-composition-control --distillate-comp-sp 0.0509385134 --distillate-comp-kc 500 --distillate-comp-ti 600 --reflux-cmd-min 2000 --reflux-cmd-max 10000 --enable-bottoms-composition-control --bottoms-comp-component C5 --bottoms-comp-sp 0.1666656867 --bottoms-comp-kc -500 --bottoms-comp-ti 600 --bottoms-comp-mv boilup --boilup-cmd-min 3000 --boilup-cmd-max 15000` | P=227.766; xD=0.124855; xB=0.159838; R=5996.64; Vb=11747.74 |

## Recent Runs (Latest 60)

| Run ID | Status | CLI Known | t_final(s) | P_top | xD | xB | Reflux | Boilup | D | B | Summary CSV |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `20260215_200510` | `ok` | Yes | 600.0 | 161.122 |  |  |  |  | 3338.94 | 5159.30 | `logs/column_summary_20260215_200510.csv` |
| `20260215_185348` | `ok` | Yes |  | 170.842 | 0.100599 | 0.161124 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_185348.csv` |
| `20260215_174906` | `ok` | Yes |  | 170.842 | 0.100599 | 0.161124 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_174906.csv` |
| `20260215_170604` | `ok` | Yes |  | 170.842 | 0.100599 | 0.161124 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_170604.csv` |
| `20260215_162944` | `ok` | Yes |  | 221.227 | 0.236757 | 0.152549 | 4439.42 | 7807.51 |  |  | `logs/feasibility_trim_search_20260215_162944.csv` |
| `20260215_160316` | `ok` | Yes |  | 170.842 | 0.100599 | 0.161124 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_160316.csv` |
| `20260215_144747` | `ok` | Yes |  | 221.227 | 0.236757 | 0.152549 | 4439.42 | 7807.51 |  |  | `logs/feasibility_trim_search_20260215_144747.csv` |
| `20260215_135110` | `ok` | Yes |  | 230.868 | 0.105845 | 0.161138 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_135110.csv` |
| `20260215_125538` | `ok` | Yes |  | 223.942 | 0.094066 | 0.157059 | 13854.55 | 10243.77 |  |  | `logs/feasibility_trim_search_20260215_125538.csv` |
| `20260215_121942` | `ok` | Yes |  | 218.440 | 0.050939 | 0.166666 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_121942.csv` |
| `20260215_114500` | `ok` | Yes |  | 140.380 | 0.090234 | 0.166502 | 11853.78 | 14532.31 |  |  | `logs/feasibility_trim_search_20260215_114500.csv` |
| `20260215_105634` | `ok` | Yes | 240.0 | 226.549 |  |  |  |  | 2380.99 | 4761.98 | `logs/column_summary_20260215_105634.csv` |
| `20260215_105542` | `ok` | Yes |  | 219.319 | 0.111417 | 0.160999 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_105542.csv` |
| `20260215_094545` | `ok` | Yes |  | 216.512 | 0.060084 | 0.165308 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_094545.csv` |
| `20260215_091428` | `ok` | Yes |  | 135.474 | 0.069226 | 0.164702 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_091428.csv` |
| `20260215_090609` | `ok` | Yes |  | 162.674 | 0.065458 | 0.166744 | 3203.96 | 14836.37 |  |  | `logs/feasibility_trim_search_20260215_090609.csv` |
| `20260215_085820` | `ok` | Yes | 240.0 | 140.380 |  |  |  |  | 2380.99 | 4761.98 | `logs/column_summary_20260215_085820.csv` |
| `20260215_085803` | `ok` | Yes |  | 184.004 | 0.113799 | 0.161443 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_085803.csv` |
| `20260215_084739` | `ok` | Yes |  | 164.931 | 0.058655 | 0.165752 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_084739.csv` |
| `20260215_084643` | `ok` | Yes |  | 180.824 | 0.071418 | 0.166766 | 3203.96 | 14836.37 |  |  | `logs/feasibility_trim_search_20260215_084643.csv` |
| `20260215_083445` | `ok` | Yes |  | 162.674 | 0.065458 | 0.166744 | 3203.96 | 14836.37 |  |  | `logs/feasibility_trim_search_20260215_083445.csv` |
| `20260215_073349` | `ok` | Yes |  | 163.465 | 0.050939 | 0.166659 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_073349.csv` |
| `20260215_073241` | `ok` | Yes |  | 218.440 | 0.050939 | 0.166666 | 5952.48 | 11743.50 |  |  | `logs/feasibility_trim_search_20260215_073241.csv` |
| `20260215_071617` | `ok` | Yes | 0.2 | 218.440 |  |  |  |  | 2380.99 | 4761.98 | `logs/column_summary_20260215_071617.csv` |
| `20260215_070444` | `ok` | Yes | 0.2 | 218.440 |  |  |  |  | 2380.99 | 4761.98 | `logs/column_summary_20260215_070444.csv` |
| `20260214_215800` | `ok` | Yes | 1200.0 | 233.076 | 0.403354 | 0.141329 | 2305.90 | 11769.47 | 3931.94 | 3402.69 | `logs/column_summary_20260214_215800.csv` |
| `20260214_214819` | `ok` | Yes | 300.0 | 237.554 | 0.126920 | 0.159907 | 5997.35 | 11747.72 | 3645.36 | 4981.79 | `logs/column_summary_20260214_214819.csv` |
| `20260214_211744` | `ok` | No | 860.0 | 221.466 | 0.287141 | 0.147383 | 2974.01 | 11760.07 | 3932.23 | 4205.63 | `logs/column_summary_20260214_211744.csv` |
| `20260214_205627` | `ok` | Yes | 380.0 | 175.759 | 0.152800 | 0.157903 | 6015.87 | 11749.27 | 3745.19 | 5238.41 | `logs/column_summary_20260214_205627.csv` |
| `20260214_203414` | `ok` | Yes | 1020.0 | 172.836 | 0.358273 | 0.143344 | 2776.02 | 11807.06 | 3687.48 | 3974.78 | `logs/column_summary_20260214_203414.csv` |
| `20260214_185352` | `ok` | No | 2000.0 | 220.046 | 0.586632 | 0.124213 | 3330.93 | 11209.36 | 2984.63 | 4330.70 | `logs/column_summary_20260214_185352.csv` |
| `20260214_154958` | `ok` | No | 1600.0 | 219.186 | 0.569022 | 0.134365 | 2000.00 | 11869.90 | 3718.24 | 3383.62 | `logs/column_summary_20260214_154958.csv` |
| `20260214_150239` | `ok` | Yes | 1200.0 | 226.677 | 0.388611 | 0.139502 | 2854.31 | 11770.92 | 3383.70 | 3931.69 | `logs/column_summary_20260214_150239.csv` |
| `20260214_145025` | `ok` | Yes | 300.0 | 227.766 | 0.124855 | 0.159838 | 5996.64 | 11747.74 | 2901.59 | 5149.02 | `logs/column_summary_20260214_145025.csv` |
| `20260214_141525` | `ok` | No | 600.0 | 226.123 | 0.165911 |  | 2932.08 |  | 2241.44 | 6300.10 | `logs/column_summary_20260214_141525.csv` |
| `20260214_081707` | `ok` | No | 600.0 | 223.255 | 0.165954 | 0.150771 | 3367.98 | 11755.32 | 2194.91 | 6315.36 | `logs/column_summary_20260214_081707.csv` |
| `20260213_212421` | `ok` | No | 900.0 | 223.744 | 0.186236 | 0.140056 | 6075.24 | 11782.80 | 168.17 | 6778.61 | `logs/column_summary_20260213_212421.csv` |
| `20260213_204636` | `ok` | No | 900.0 | 220.604 | 0.224331 | 0.141993 | 3001.99 | 11781.47 | 2237.11 | 5421.74 | `logs/column_summary_20260213_204636.csv` |
| `20260213_182452` | `ok` | No | 3000.0 | 223.699 | 0.700705 | 0.095589 | 2142.86 | 11911.48 | 2080.27 | 4974.18 | `logs/column_summary_20260213_182452.csv` |
| `20260213_182007` | `ok` | No | 120.0 | 216.362 | 0.073148 | 0.163512 | 5010.20 | 11753.22 | 2225.00 | 5147.75 | `logs/column_summary_20260213_182007.csv` |
| `20260213_181509` | `ok` | No | 120.0 | 216.362 | 0.073148 | 0.163512 | 5010.20 | 11753.22 | 2225.00 | 5147.75 | `logs/column_summary_20260213_181509.csv` |
| `20260213_163354` | `ok` | No | 2400.0 | 219.380 | 0.408718 | 0.103261 | 4332.63 | 9000.00 | 1250.33 | 5929.63 | `logs/column_summary_20260213_163354.csv` |
| `20260213_155419` | `ok` | No | 120.0 | 216.374 | 0.073138 |  | 5012.62 |  | 2225.93 | 5147.34 | `logs/column_summary_20260213_155419.csv` |
| `20260213_154230` | `ok` | No | 120.0 | 215.177 | 0.073511 |  | 5209.22 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_154230.csv` |
| `20260213_153632` | `ok` | No | 120.0 | 169.007 | 0.073067 |  | 6143.21 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_153632.csv` |
| `20260213_153305` | `ok` | No | 120.0 | 226.129 |  |  |  |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_153305.csv` |
| `20260213_152121` | `ok` | No | 120.0 | 231.097 | 0.074135 |  | 5490.05 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_152121.csv` |
| `20260213_151505` | `ok` | No | 120.0 | 227.611 | 0.072783 |  | 5757.07 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_151505.csv` |
| `20260213_142703` | `ok` | No | 900.0 | 166.964 | 0.237410 |  | 2527.55 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_142703.csv` |
| `20260213_141158` | `ok` | No | 60.0 | 160.068 | 0.059376 |  | 5952.06 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_141158.csv` |
| `20260213_140805` | `ok` | No | 60.0 | 213.982 | 0.058902 |  | 5952.11 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_140805.csv` |
| `20260213_134558` | `ok` | No | 300.0 | 216.361 | 0.119504 |  | 4493.96 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_134558.csv` |
| `20260213_134248` | `ok` | No | 5.0 | 203.730 | 0.051009 |  | 5952.89 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_134248.csv` |
| `20260213_134032` | `ok` | No | 0.2 | 207.185 | 0.050939 |  | 5940.57 |  | 2380.99 | 4761.98 | `logs/column_summary_20260213_134032.csv` |
| `20260213_131826` | `ok` | No | 300.0 | 219.447 | 0.112909 |  | 6000.00 |  | 2313.00 | 5133.03 | `logs/column_summary_20260213_131826.csv` |
| `20260213_130650` | `ok` | No | 300.0 | 219.797 | 0.123995 |  | 4531.43 |  | 2801.76 | 4978.23 | `logs/column_summary_20260213_130650.csv` |
| `20260213_125413` | `ok` | No | 300.0 | 219.470 |  |  |  |  | 2794.06 | 4992.97 | `logs/column_summary_20260213_125413.csv` |
| `20260213_123242` | `ok` | No | 300.0 | 219.399 |  |  |  |  | 2649.79 | 4912.35 | `logs/column_summary_20260213_123242.csv` |
| `20260213_121834` | `ok` | No | 300.0 | 220.033 |  |  |  |  | 2516.74 | 4837.75 | `logs/column_summary_20260213_121834.csv` |
| `20260213_120416` | `ok` | No | 300.0 | 239.402 |  |  |  |  | 2508.49 | 4838.92 | `logs/column_summary_20260213_120416.csv` |
