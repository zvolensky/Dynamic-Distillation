# Invalid continuation attempt

This run was stopped after 30 simulated seconds because
`--init-align-top-liquid-to-condensate` was inadvertently applied after the
native checkpoint load. It changed the distillate-drum water mole fraction
from 0.0348516 at the source checkpoint to 0.0562816 at restart, so the run is
not a bumpless continuation and must not be used for model assessment.

The replacement run omits all initialization transforms and reloads the
original 60-second checkpoint.
