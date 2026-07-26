# DD-105 Frozen Pressure-Enabled First-Step Contract

- Payload SHA-256: `4cc0739dd4344529954a0470d85db9f29c128d42c45ac42fb711ab5b28d0dcad`
- Independent steps: `1.0 s`, `0.5 s`
- System: exact-storage `42 x 42` backward Euler
- Jacobian: frozen 20-color central difference
- Live calls during preparation: `False`

The endpoint energy balance uses the exact live `U_next-U_previous`; the fixed-pressure storage gradient is prohibited. Commit before one execution. No retry, trajectory, or controller is authorized.
