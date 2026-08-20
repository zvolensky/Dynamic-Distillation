# DD-274 Dynamic-Pressure Thirty-Second Contract

- Payload SHA-256: `2e7bcfb70df658152ff2d369e91ef4243d01f3e798b3824f1f0056db6cf3c68b`
- Start: `DD-271 endpoint at 30 seconds`.
- Nominal path: `120` x `0.25 s`.
- Condenser duty: `-50894825.691565 BTU/h` fixed.
- Reflux-drum pressure is dynamic; no pressure controller is active.
- Drum and sump geometry-based level controllers remain active.
- One fresh 16-color Jacobian is allowed per root; final half-step refinement is mandatory.
- Retry, alternate grid, tuning, fallback, or extension: `False`.
