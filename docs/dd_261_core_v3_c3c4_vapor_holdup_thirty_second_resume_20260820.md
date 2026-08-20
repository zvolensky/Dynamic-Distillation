# DD-261 Journaled Thirty-Second Vapor-Holdup Result

- Classification: `journaled_thirty_second_vapor_holdup_trajectory_failed`
- Decision: `retain_dd260_endpoint_81_boundary`
- Endpoint path: `81 recovered + 39 continued = 120`.
- Final condenser duty: `-51.000770 MMBTU/h`
- Final inventory change: `5.952478470e-02 lbmol`
- Component identity: `2.597303e-06 lbmol`
- Energy identity relative: `8.983373e-04`
- Combined provider calls: `999360`
- Continuation wall: `98.367 s`; segment simulation/wall: `0.09912`
- Continuity: `{'temperature_F': 2.6451907075397685e-05, 'pressure_psia': 8.767575820911588e-07, 'composition': 3.3427078410808164e-07, 'flow_relative': 4.856917226649374e-06, 'phase_inventory_relative': 3.2877567175986805e-06, 'duty_relative': 3.868887963009856e-08}`
- Final refinement: `{'maximum_component_inventory_difference_lbmol': 2.663431359906099e-07, 'component_inventory_difference_l1_lbmol': 1.6520506458863465e-06, 'signed_total_inventory_difference_lbmol': 1.541301808405393e-14, 'temperature_difference_F': 5.371521183406003e-08, 'pressure_difference_psia': 1.6389094525948167e-09, 'liquid_flow_relative_difference': 1.2624285128064069e-08, 'vapor_flow_relative_difference': 1.5527368810037445e-09, 'phase_transfer_scaled_difference': 1.6781468871214702e-09, 'duty_relative_difference': 1.011991235505722e-10}`
- Gates: `{'combined_path_complete': True, 'scientific_endpoints': True, 'positive_monotonic_accumulation': True, 'component_identity': False, 'energy_identity': False, 'temperature_ordering': True, 'continuation_continuity': True, 'final_refinement': True, 'provider': True, 'journal_complete': True, 'report_complete': True, 'combined_call_count': True, 'continuation_wall_clock': True, 'no_retry_or_controller': True}`

## Final stage profile

| Volume | T (F) | P (psia) | N_L | N_V | L out | V out | xC3 | xC4 | xC5 | yC3 | yC4 | yC5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reflux_drum | 120.4465 | 220.44000 | 1388.90476 | 138.50449 |  |  | 0.879530 | 0.120428 | 0.000042 | 0.946059 | 0.053931 | 0.000010 |
| rectifying_volume_1 | 129.9460 | 220.48769 | 38.03157 | 49.26517 | 5659.603 | 8472.773 | 0.754841 | 0.244994 | 0.000165 | 0.879527 | 0.120431 | 0.000042 |
| rectifying_volume_2 | 141.0374 | 220.53700 | 34.29421 | 12.74984 | 5439.100 | 8179.886 | 0.622296 | 0.377261 | 0.000443 | 0.793251 | 0.206622 | 0.000127 |
| rectifying_volume_3 | 151.4110 | 220.58616 | 33.36301 | 12.53172 | 5314.452 | 7959.374 | 0.509639 | 0.489373 | 0.000988 | 0.703735 | 0.295949 | 0.000316 |
| rectifying_volume_4 | 159.4352 | 220.63562 | 32.78594 | 12.37648 | 5257.676 | 7834.718 | 0.429184 | 0.568854 | 0.001962 | 0.628609 | 0.370707 | 0.000684 |
| rectifying_volume_5 | 164.8828 | 220.68542 | 32.39051 | 12.28286 | 5233.422 | 7777.937 | 0.377825 | 0.618542 | 0.003634 | 0.575089 | 0.423571 | 0.001340 |
| rectifying_volume_6 | 168.3451 | 220.73557 | 32.17726 | 12.22462 | 5219.704 | 7753.680 | 0.346988 | 0.646555 | 0.006457 | 0.540878 | 0.456656 | 0.002466 |
| rectifying_volume_7 | 170.5576 | 220.78596 | 32.03899 | 12.18776 | 5205.490 | 7739.961 | 0.328860 | 0.659941 | 0.011199 | 0.520370 | 0.475261 | 0.004368 |
| rectifying_volume_8 | 172.1292 | 220.83643 | 31.88949 | 12.16293 | 5184.186 | 7725.747 | 0.317925 | 0.662948 | 0.019127 | 0.508475 | 0.483965 | 0.007560 |
| rectifying_volume_9 | 173.5309 | 220.88682 | 31.68698 | 12.14113 | 5149.443 | 7704.444 | 0.310592 | 0.657115 | 0.032293 | 0.501616 | 0.485499 | 0.012885 |
| rectifying_volume_10 | 175.1692 | 220.93704 | 31.41501 | 12.11233 | 5092.942 | 7669.704 | 0.304458 | 0.641652 | 0.053890 | 0.497529 | 0.480774 | 0.021697 |
| feed_tray | 177.4754 | 221.01216 | 45.88240 | 10.90239 | 12225.695 | 7613.206 | 0.297717 | 0.613739 | 0.088544 | 0.494821 | 0.469111 | 0.036068 |
| stripping_volume_1 | 180.9783 | 221.08784 | 45.68891 | 10.84907 | 12246.363 | 7595.917 | 0.269073 | 0.641024 | 0.089903 | 0.457236 | 0.504819 | 0.037945 |
| stripping_volume_2 | 185.1751 | 221.16457 | 45.51034 | 10.78414 | 12282.951 | 7616.908 | 0.235544 | 0.672965 | 0.091491 | 0.410761 | 0.548964 | 0.040275 |
| stripping_volume_3 | 189.9321 | 221.24256 | 45.30158 | 10.71558 | 12339.064 | 7654.211 | 0.198572 | 0.708080 | 0.093347 | 0.356285 | 0.600646 | 0.043069 |
| stripping_volume_4 | 195.0111 | 221.31215 | 53.47169 | 12.08670 | 12413.353 | 7711.387 | 0.160334 | 0.743930 | 0.095736 | 0.296250 | 0.657350 | 0.046400 |
| stripping_volume_5 | 200.1560 | 221.38311 | 53.17124 | 12.01420 | 12498.138 | 7787.006 | 0.123252 | 0.777167 | 0.099582 | 0.234361 | 0.714974 | 0.050666 |
| stripping_volume_6 | 205.2254 | 221.45605 | 53.20228 | 11.91744 | 12574.888 | 7872.957 | 0.089386 | 0.803104 | 0.107510 | 0.174695 | 0.768042 | 0.057263 |
| stripping_volume_7 | 210.4219 | 221.53033 | 52.76649 | 11.85036 | 12609.342 | 7950.563 | 0.060029 | 0.813732 | 0.126239 | 0.120636 | 0.809149 | 0.070215 |
| combined_reboiler_sump | 216.6629 | 221.55567 | 794.00128 | 73.97619 |  | 7985.553 | 0.035642 | 0.792711 | 0.171647 | 0.074146 | 0.825903 | 0.099951 |

DD-260 rerun, retry, controller, fallback, or extension: `False`
