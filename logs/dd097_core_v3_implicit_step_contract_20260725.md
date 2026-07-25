# DD-097 Frozen Core V3 Implicit-Step Contract

- Payload SHA-256: `a87de97aeb958a392eef72c43afdcf1e4bc2d807d015ca6cead13d1866b01d20`
- Preparation base commit: `2397cabae66721b4a5d5c3f6b1fb0a0993ad1438`
- Solver: `least_squares(method=trf)`
- Checks: zero-rate recovery, independent `1.0 s` and `0.5 s` steps
- Live property evaluation during preparation: `False`
- Dynamic step during preparation: `False`

The contract must be committed before its one live execution.
