# Proposed follow-up for Clapeyron.jl issue #608

Thank you. An explicit status API would address the phase-row ambiguity.

For compatibility with multiphase algorithms, I would prefer that the API distinguish the number of active phases from their row indices:

```julia
n_active_phases(flash)::Int
active_phase_indices(flash)::Vector{Int}
identify_phase(flash, i)::Symbol  # existing API
```

An all-in-one alternative could return a named tuple rather than a positional tuple:

```julia
flash_status(flash) = (
    active_indices = Int[...],
    phase_labels = Symbol[...],
    fractions = [...],
)
```

This avoids making a singular `active_phase_index` ambiguous when more than one phase is active, and avoids using `active_phases(flash)::Int` for both a count and a collection.

For Michelsen/Rachford-Rice flashes, exposing the discarded K-values would also solve our dynamic-model requirement. We use the incipient or extrapolated K-values to calculate an equilibrium target even when the current state is single phase. They could be exposed as optional algorithm-specific metadata, for example:

```julia
discarded_K(flash)::Union{Nothing,Vector}
```

or as a documented field in `flash.metadata`. The documentation should make clear that these K-values describe the discarded/nonexistent phase and are intended for stability, incipient-phase, or algorithmic calculations; they are not evidence that the second phase physically exists.

This separation would let callers answer two different questions reliably:

1. Which phases are physically active in this flash result?
2. What equilibrium K-values did a Michelsen/RR algorithm converge before declaring a single phase?
