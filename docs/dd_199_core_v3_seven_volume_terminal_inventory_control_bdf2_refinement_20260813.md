# DD-199 Controlled BDF2 Short-Refinement Result

## Decision

DD-199 is aborted before a complete trajectory or scientific result. It shall
not be rerun or reclassified.

## Stop

The coarse path completes its backward-Euler startup and first BDF2 endpoint.
Before the third root is evaluated, the trajectory handoff raises:

`AttributeError: 'TerminalInventoryControlBDF2Evaluation' object has no attribute 'endpoint_inventory_lbmol'`

The trajectory kernel correctly reads the direct endpoint fields of a
backward-Euler evaluation, but after the first BDF2 endpoint it tries to use
the same direct layout again. BDF2 endpoint inventory, internal energy, and PI
memory are stored under `evaluation.kinematics`. No result artifact, complete
path, shared-time comparison, or model acceptance decision is produced.

## Meaning

This is a trajectory-adapter defect, not evidence of failed equations,
thermodynamics, nonlinear closure, or BDF2 accuracy. The two roots completed
before the handoff are insufficient to classify any frozen scientific gate.

The correction is limited to method-aware accessors for accepted inventory,
provider-derived internal energy, and PI memory. A regression must chain at
least three genuine BDF2-shaped evaluations. A separately numbered successor
may repeat the unchanged DD-199 scientific contract after the correction is
committed; DD-199 itself remains retired.

