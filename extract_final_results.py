#!/usr/bin/env python
import pandas as pd
import os

os.chdir('logs/c3c4_30_minute_controlled_dynamic_run_20260708')

# Load summary and profile
summary = pd.read_csv('column_summary_20260708_161124.csv')
profile = pd.read_csv('column_profile_20260708_161124.csv')

# Get final time
final_time = summary['time_s'].max()
final_summary = summary[summary['time_s'] == final_time].iloc[0]
final_profile = profile[profile['time_s'] == final_time]

print("=" * 70)
print("30-MINUTE CONTROLLED DYNAMIC DISTILLATION RUN - FINAL RESULTS")
print("=" * 70)
print()

print("1. STEADY STATE SCORE")
print("-" * 70)
# Check if system appears to be at steady state
# Look at magnitude of state rates from final profile
mass_residual = final_profile['stage_mass_balance_resid_lbmolps'].abs().mean()
energy_residual = final_profile['stage_energy_balance_resid_BTUps'].abs().mean()
print(f"   Mean mass balance residual: {mass_residual:.6f} lbmol/s")
print(f"   Mean energy balance residual: {energy_residual:.2f} BTU/s")
print(f"   Status: {'Good convergence' if energy_residual < 500 else 'Still transient'}")
print()

print("2. DISTILLATE CONDITIONS")
print("-" * 70)
dist_row = final_profile[final_profile['stage'] == 0]
if not dist_row.empty:
    dist = dist_row.iloc[0]
    print(f"   Temperature: {final_summary['T_Distillate_F']:.2f} °F")
    print(f"   Pressure: {final_summary['P_top_psia']:.2f} psia")
    print(f"   Composition (mole fraction):")
    print(f"      n-Propane: {dist['Distillate_x_n_Propane']:.6f}")
    print(f"      n-Butane:  {dist['Distillate_x_n_Butane']:.6f}")
    print(f"      n-Pentane: {dist['Distillate_x_n_Pentane']:.6f}")
print()

print("3. CONDENSER DUTY")
print("-" * 70)
q_cond = final_summary['Q_cond_used_BTUph']
print(f"   Condenser duty (final): {q_cond:,.0f} BTU/hr")
print(f"   (Negative = heat removal, as expected for condenser)")
print()

print("4. BOTTOMS CONDITIONS")
print("-" * 70)
bottoms_row = final_profile[final_profile['node_type'] == 'sump']
if not bottoms_row.empty:
    bottoms = bottoms_row.iloc[0]
    print(f"   Temperature: {bottoms['T_sump_F']:.2f} °F")
    print(f"   Pressure: {final_summary['P_bot_psia']:.2f} psia")
    print(f"   Composition (mole fraction):")
    print(f"      n-Propane: {bottoms['Bottoms_x_n_Propane']:.6f}")
    print(f"      n-Butane:  {bottoms['Bottoms_x_n_Butane']:.6f}")
    print(f"      n-Pentane: {bottoms['Bottoms_x_n_Pentane']:.6f}")
print()

print("5. REBOILER DUTY")
print("-" * 70)
q_reb = final_summary['Q_reb_used_BTUph']
print(f"   Reboiler duty (final): {q_reb:,.0f} BTU/hr")
print(f"   (Positive = heat input, as expected for reboiler)")
print()

print("6. STAGE PROFILES (T, P, Composition at t=1800 sec)")
print("-" * 70)
print(f"{'Stage':>5} {'T (°F)':>9} {'P (psia)':>10} {'x_C3':>9} {'x_C4':>9} {'x_C5':>9}")
print("-" * 70)

# Print distillate
print(f"{'D':>5} {final_summary['T_Distillate_F']:>9.2f} {final_summary['P_top_psia']:>10.2f}  {dist['Distillate_x_n_Propane']:>9.6f} {dist['Distillate_x_n_Butane']:>9.6f} {dist['Distillate_x_n_Pentane']:>9.6f}")

# Print stages 1-20
stages = final_profile[(final_profile['stage'] > 0) & (final_profile['stage'] < 21) & (final_profile['node_type'] != 'sump')].sort_values('stage')
for idx, row in stages.iterrows():
    print(f"{int(row['stage']):>5.0f} {row['T_F']:>9.2f} {row['P_psia_hyd']:>10.2f}  {row['x_n_Propane']:>9.6f} {row['x_n_Butane']:>9.6f} {row['x_n_Pentane']:>9.6f}")

# Print bottoms
if not bottoms_row.empty:
    print(f"{'B':>5} {bottoms['T_sump_F']:>9.2f} {final_summary['P_bot_psia']:>10.2f}  {bottoms['Bottoms_x_n_Propane']:>9.6f} {bottoms['Bottoms_x_n_Butane']:>9.6f} {bottoms['Bottoms_x_n_Pentane']:>9.6f}")

print()
print("=" * 70)
print("SUMMARY NOTES")
print("=" * 70)
print(f"Run duration: {final_summary['time_s']:.1f} seconds (30 minutes)")
print(f"Top pressure control setpoint: 222.62 psia")
print(f"Final top pressure: {final_summary['P_top_psia']:.2f} psia")
print(f"Pressure control error: {final_summary['P_top_psia'] - 222.62:.2f} psia")
print(f"Level control - Top holdup (true-level): {final_summary['Top_level_ctrl_pv']:.1f} lbmol")
print(f"Level control - Bottom holdup (true-level): {final_summary['Bottom_level_ctrl_pv']:.1f} lbmol")
print()
