# DD-096 Frozen Core V3 Dynamic DAE Numerical Contract

- Payload SHA-256: `f1fb87d34fc4efed252816a4016c7dbdaed4bbe7961bed76e8459ddf582c0bac`
- Preparation base commit: `bba08b2d6bff847b7654619e6a18cb87dbfc3f09`
- Dynamic system: `38 x 38` implicit leading system
- Storage derivative steps: `1e-5`, `5e-6`
- Leading-Jacobian steps: `1e-5`, `5e-6`
- Live property evaluation during preparation: `False`
- Dynamic integration during preparation: `False`

## Authorization

Commit this contract before its one live execution. No integration, perturbation, controller, or alternate numerical campaign is authorized.
