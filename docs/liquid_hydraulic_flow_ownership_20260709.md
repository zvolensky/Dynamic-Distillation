# Liquid Hydraulic Flow Ownership Finding - 2026-07-09

## Context

External review of the post feed-flash K=1 fix runs identified a suspiciously linear loss of liquid inventory on the feed-bearing tray. The observed drain rate was effectively constant through the 900 s profile-flow run, even though the Francis-weir hydraulic candidate should decrease as liquid holdup decreases.

## Finding

The Francis-weir calculation is not the source of the linear drain. The hydraulic candidate is computed and responds to holdup, but the current accepted hydraulic-mode recipe keeps liquid-hydraulic override disabled unless it is explicitly requested.

In that recipe:

- `L_out_hyd` is a diagnostic hydraulic candidate.
- `L_out_used` is the liquid traffic actually marched by the model.
- With override disabled, `L_out_used` remains the profile/imported flow.

For the 300 s product-draw-fixed profile-flow run:

| Metric | Result |
|---|---:|
| feed-bearing stage | 12 |
| final feed-stage liquid inventory | 38.3486 lbmol |
| `dMLdt_total` | -0.042378358348 lbmol/s, constant |
| `L_out_used` at 300 s | 12372.19 lbmol/h |
| `L_out_hyd` at 300 s | 4169.21 lbmol/h |
| max `L_out_used - L_out_hyd` | 8202.98 lbmol/h |
| final steady-state score | 2.269 |

This explains the linear depletion: the model is marching profile liquid flow while merely logging the hydraulic candidate.

## Controlled Runs

Two generic liquid-hydraulic override tests were run after the product-draw composition fix.

### Full Francis override, alpha = 1.0, 300 s

Run directory:

`logs/c3c4_stage2_productdrawfix_liqhyd_a1_300s_20260709`

Result:

- Bounded through 300 s.
- Feed-stage liquid inventory did not dry out.
- Final feed-stage liquid inventory rose to 62.9904 lbmol.
- Final score was 2.714, worse than the profile-flow 300 s score.
- Worst state moved to lower-column vapor, stage 19 n-Pentane.
- Feed-stage energy residual and inventory update excursions were larger than desired.

Conclusion: full immediate liquid-hydraulic override fixes the deterministic drain but is too abrupt for this recipe.

### Partial Francis override, alpha = 0.25, 300 s, 900 s, and 1800 s

Run directories:

`logs/c3c4_stage2_productdrawfix_liqhyd_a025_300s_20260709`

`logs/c3c4_stage2_productdrawfix_liqhyd_a025_900s_20260709`

`logs/c3c4_stage2_productdrawfix_liqhyd_a025_1800s_20260709`

300 s result:

- Bounded through 300 s.
- Feed-stage liquid inventory stayed near the seed, ending at 54.3313 lbmol.
- Final score was 2.543.
- Worst state moved to tray vapor, stage 18 n-Propane.

900 s result:

| Metric | Result |
|---|---:|
| final feed-stage liquid inventory | 70.0968 lbmol |
| min feed-stage liquid inventory | 51.0621 lbmol |
| final steady-state score | 1.5449 |
| best score after 600 s | 0.8882 |
| final `K_state - K_thermo` max abs | 1.6928 |
| max `L_out_used - L_out_hyd` | 5489.08 lbmol/h |

Conclusion: partial liquid hydraulics removes the deterministic feed-stage dryout and is more viable than full immediate override, but it does not yet produce a clean accepted run. K-state drift remains a separate unresolved problem.

1800 s follow-up:

| Metric | Result |
|---|---:|
| final feed-stage liquid inventory | 70.0984 lbmol |
| min feed-stage liquid inventory | 51.0621 lbmol |
| final steady-state score | 1.1798 |
| score at 1500 s | 0.9165 |
| best score in final third | 0.5917 |
| final `K_state - K_thermo` max abs | 0.7894 |

Conclusion: the 900 s score uptick did not become a hard blow-up by 1800 s. The partial-hydraulic recipe remains bounded, avoids deterministic feed-stage dryout, and the K-state mismatch improves by the end of the 1800 s run. However, the score is still oscillatory rather than settled, so a single final score is not a sufficient acceptance criterion.

## Current Interpretation

This is progress, not a dead end.

The model had at least two independent structural issues:

1. Product draws were using static component specifications instead of live vessel compositions. That has been fixed.
2. The current profile-flow recipe was not actually using liquid hydraulics, causing deterministic feed-stage inventory depletion. This is now diagnosed and experimentally confirmed.

However, activating liquid hydraulics introduces or reveals coupled vapor/composition transients. The next work should not return to initializer tuning. It should focus on making liquid-flow handoff from profile to hydraulic behavior smoother and dynamically acceptable.

## Recommended Next Step

Implement or tune a staged liquid-hydraulic handoff:

- Start with profile liquid traffic.
- Ramp the Francis override gradually.
- Gate the ramp using existing dynamic score or residual signals.
- Keep the logic generic over all internal stages.
- Continue to audit `L_out_used - L_out_hyd`, feed-stage liquid inventory, dynamic gate score, and K-state drift.

The acceptance criterion should require:

- no deterministic tray dryout, and
- dynamic gate score below threshold over the final window, and
- a stable or non-worsening score trend over the final portion of the run.
