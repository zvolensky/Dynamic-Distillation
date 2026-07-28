# DD-123 Core V3 Controlled-Terminal Dynamic Contract

- Classification: `passed`
- Decision: `authorize_frozen_live_controlled_terminal_handoff_contract`
- Three-component system: `50 x 50`, rank `50`
- Generic two-component system: `40 x 40`, rank `40`
- Differential states: conserved component inventories, four lower internal energies, and two level-controller memories
- Controller outputs: positive distillate and bottoms rates
- Geometry: horizontal drum with two hemispherical heads and vertical cylindrical sump
- Bumpless outputs: `D=2255.740878`, `B=4887.233122 lbmol/h`
- Property call, nonlinear solve, timestep, or dynamics: `False`

The DD-122 terminal amounts remain inventory setpoints until the live property audit calculates their geometry-based physical levels. Passing authorizes only one frozen live zero-time controller-handoff audit before any timestep.
