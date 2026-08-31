# Core V3 pressure and distillate-composition controls

Core V3 now supports two additional implicit PI controllers alongside the existing terminal level loops:

- Reflux-drum pressure manipulates condenser-duty magnitude.
- Distillate n-butane mole fraction manipulates reflux flow.
- Reflux-drum and sump levels continue to manipulate distillate and bottoms flow, respectively.
- Reboiler duty remains fixed.

The regulatory successor has 265 solve variables and 265 residual rows. Its structural rank is 265. The controller states, rates, outputs, tuning, setpoints, and activation flags are persisted in native Core V3 checkpoints. Older two-controller checkpoints are upgraded bumplessly when `--regulatory-control` is selected. Once active, the controls are inherited automatically by later continuation runs.

## Initial tuning and limits

- Pressure: `Kc = 300,000 BTU/h/psi`, `Ti = 180 s`.
- Distillate n-butane: `Kc = 5,000 lbmol/h/mole-fraction`, `Ti = 600 s`.
- Condenser-duty magnitude and reflux are limited to `0.5–1.5` times their activation references.
- On first activation, omitted setpoints are taken from the checkpoint endpoint and both PI memories are back-calculated to preserve the existing duty and reflux outputs.

## Qualification result

The controls were activated at the accepted 0.5 s checkpoint with pressure `221.321226 psia`, condenser duty `-50.894826 MMBtu/h`, distillate n-butane `0.119871752`, and reflux `5952.48 lbmol/h`.

- First endpoint: residual `2.65e-12`, numerical rank `265/265`, condition number `4.74e6`.
- Activation changes: pressure `-0.000129 psi`, duty `+38.8 BTU/h`, reflux `+0.000759 lbmol/h`, n-butane `+1.52e-7` mole fraction.
- The inherited restart and 600 s unchanged-setpoint hold accepted every endpoint.
- Over the full hold, pressure stayed within `0.05313 psi` of setpoint, reached a smooth minimum, and recovered.
- Final steady-state score: `0.7001`; steady-state flag: `true`.
- Maximum logged residual: `2.85e-12`; condition number range: `4.668e6–4.736e6`.
- Final level fractions: reflux drum `0.49747`, sump `0.50005`.

Accepted controlled checkpoint:

`logs/core_v3_regulatory_bumpless_hold600s_20260830/core_v3_checkpoint_20260830_142858.npz`

## Runner options

Activate from an older Core V3 checkpoint with `--regulatory-control`. Optional tuning/setpoint overrides are:

- `--pressure-sp-psia`
- `--pressure-kc-btuph-per-psia`
- `--pressure-ti-sec`
- `--composition-component`
- `--composition-sp-molfrac`
- `--composition-kc-lbmolph-per-molfrac`
- `--composition-ti-sec`

A continuation from an active checkpoint inherits both controllers and their memories automatically. Deactivation from an active checkpoint is rejected because silently returning to fixed duty and reflux would not be a bumpless transition.

## +5 F feed-temperature disturbance result

Status: **executed and stopped at the pressure hard gate; not accepted**.

The next experiment starts from the accepted controlled checkpoint above. At disturbance time zero, the feed temperature changes from `174.999 F` to `179.999 F`. The following quantities remain unchanged:

- feed pressure: `232.06 psia`;
- feed component rates: n-propane `2380.99`, n-butane `3968.32`, and n-pentane `793.664 lbmol/h`;
- feed composition and total component flow;
- pressure and distillate-composition controller setpoints;
- all four controller tunings and memories;
- reboiler duty and the remaining boundary conditions.

Core V3 owns feed energy through `feed_enthalpy_BTUph`; changing a temperature label alone is not a disturbance. The runner must therefore evaluate liquid feed molar enthalpy at both `174.999 F` and `179.999 F`, at `232.06 psia` and the unchanged feed composition, using the governed DWSIM Peng-Robinson provider. The disturbed feed-energy rate is the unchanged component-flow total multiplied by the `179.999 F` liquid molar enthalpy. A fixed enthalpy multiplier is prohibited.

The planned primary horizon is `600 s` at the validated `0.5 s` timestep. If every hard gate passes but pressure or composition recovery is incomplete, one predeclared extension is allowed to a maximum total disturbance horizon of `1200 s`. No tuning, setpoint, limit, timestep, or disturbance change is allowed during either segment.

The disturbance record must include:

- baseline and disturbed feed molar enthalpy and total enthalpy rate;
- peak and final reflux-drum pressure error;
- peak and final distillate n-butane error;
- integrated absolute pressure and composition error;
- condenser-duty and reflux movement, including saturation margins;
- reflux-drum and sump level extrema;
- recovery/turning times and final error slopes;
- residual, rank, condition number, physicality, and controller-memory recurrence gates.

Hard acceptance gates require every endpoint to be physical, have residual below `1e-8`, numerical rank `265`, condition number below `1e8`, and controller-memory recurrence error below `1e-10`. Neither manipulated variable may reach its configured `0.5-1.5` ratio limit. The reflux-drum and sump levels must remain within `0.45-0.55`, and absolute pressure error must remain below `0.5 psi`. Distillate n-butane is logged as a response variable; it becomes a hard acceptance gate only when an actual product-quality requirement is explicitly declared for the experiment. Recovery quality is assessed against the saved pre-disturbance errors and the observed peaks.

### Execution and hard stop

The governed DWSIM Peng-Robinson calls returned baseline and disturbed liquid
feed molar enthalpies of `-5132.515936130543` and `-4924.056557372913
BTU/lbmol`, respectively. At the unchanged total flow of `7142.974 lbmol/h`,
the feed-energy boundary changed from `-36661427.88636613` to
`-35172407.96384422 BTU/h`, a `+1489019.92252191 BTU/h` step. The baseline
boundary parity error was zero.

The first disturbed solve exposed an artificial numerical restriction: the
logarithmic vapor-flow coordinates immediately above and below the feed tray
were pinned at the generic `+/-0.01` algebraic solve envelope. This was not a
physical or controller limit. Before accepting a disturbed endpoint, the
vapor-flow-only log envelope was expanded to `+/-0.05`; every other coordinate
bound and both configured `0.5-1.5` manipulated-variable limits remained
unchanged. The disturbance path also permits up to 160 nonlinear evaluations
and refreshes the colored Jacobian every five Jacobian callbacks. Ordinary
unchanged-input continuations retain their prior 40-evaluation, one-Jacobian
policy.

With those numerical-readiness provisions, the accepted `t = 0.5 s` preflight
closed with SciPy success, residual `5.319745e-12`, rank `265/265`, condition
`4.655299e6`, no active bounds, and a physical endpoint. Its pressure and
distillate n-butane errors were `-0.0325782 psi` and `+0.000125375` mole
fraction. The checkpoint is:

`logs/core_v3_feedT_plus5F_preflight160_20260830/core_v3_checkpoint_20260830_150806.npz`

The unchanged continuation was then replayed with the response-quality gates
enforced at every endpoint. The first failure occurred at `t = 87.0 s` total
disturbed time: reflux-drum pressure was `221.823624947 psia`, or
`+0.502398936 psi` above setpoint. That endpoint remained numerically and
physically sound: residual `3.912488e-13`, rank `265/265`, condition
`4.654713e6`, and physical pass. Distillate n-butane error was only
`+0.000212060`, drum and sump levels were `0.497944` and `0.499906`, condenser
duty ratio was `1.002867`, and reflux ratio was `1.000266`; all of those gates
passed. The failed endpoint therefore isolates insufficient pressure rejection
under the current tuning, rather than composition coupling, inventory control,
actuator saturation, or nonlinear-solver quality.

The primary campaign stopped at this first pressure violation. No 600-second
disturbance checkpoint is accepted, and the conditional 1200-second extension
is not authorized because an existing hard gate failed. A future run requires
a separately documented decision to retune the pressure loop, reduce the
disturbance, or revise the pressure criterion; none of those changes may be
folded into this failed frozen test.

## Pressure-gain successor result

Status: **historically stopped at a provisional composition threshold that is now retired; not a product-quality failure**.

The next experiment changes only the pressure-controller proportional gain
from `300,000` to `3,000,000 BTU/h/psi`. Pressure integral time remains `180 s`;
the composition and both level-controller tunings remain unchanged. All
setpoints, manipulated-variable limits, the `0.5 s` timestep, reboiler duty,
feed definition, and physical acceptance gates remain unchanged.

The gain follows directly from the failed test. The `+5 F` feed step adds
`1.489020 MMBTU/h`, or about `2.93%` of the `50.894826 MMBTU/h` condenser-duty
reference. Supplying approximately that proportional duty correction before a
`0.5 psi` error requires about `2.98 MMBTU/h/psi`; the frozen trial rounds this
to `3.0 MMBTU/h/psi`. Integral time is deliberately held fixed to isolate the
gain effect.

Retuning starts from the accepted undisturbed four-controller checkpoint. The
pressure PI memory is back-calculated from the saved duty and pressure error so
the gain change is bumpless; its rate predictor is made consistent with the new
gain. A `60 s` unchanged-input qualification at `0.5 s` precedes the repeated
`+5 F` disturbance. Only if all unchanged-input endpoints pass may its final
checkpoint become the disturbance source. The repeated disturbance then uses
the same `600 s` primary horizon, unchanged enthalpy boundary, and the same
hard gates as the failed baseline test. The conditional extension rule remains
unchanged and cannot be invoked after any hard-gate failure.

### Retuned execution and hard stop

The bumpless gain-change endpoint passed with a duty movement of only about
`66.8 BTU/h`, pressure movement of `+0.000074 psi`, residual `3.904657e-13`,
rank `265/265`, and condition `4.637493e6`. The following unchanged-input hold
completed the frozen 60 seconds with every endpoint accepted. Its final
pressure error was `-0.0248297 psi`, residual `9.843669e-13`, condition
`4.635338e6`, and dynamic score `0.4747`. The qualified retuned checkpoint is:

`logs/core_v3_pressure_kc3m_hold60s_20260830/core_v3_checkpoint_20260830_192026.npz`

The identical `+5 F` disturbed preflight then passed at `t = 0.5 s`, with
pressure error `-0.0226794 psi`, residual `3.729239e-12`, rank `265/265`, and
condition `4.622998e6`. Its checkpoint is:

`logs/core_v3_pressure_kc3m_feedT_plus5F_preflight_20260830/core_v3_checkpoint_20260830_192306.npz`

The stronger pressure gain corrected the original failure. The logged pressure
error rose to approximately `+0.305 psi` near `t = 120.5 s`, turned, and was
recovering thereafter; it was only `+0.131714 psi` at the eventual stop.
However, the first composition violation occurred at `t = 355.0 s`, when the
distillate n-butane error reached `+0.002001574`, just above the strict `0.002`
limit. The failed endpoint remained numerically and physically sound: residual
`8.159130e-13`, rank `265/265`, condition `4.584253e6`, and physical pass.
Drum and sump levels were `0.501798` and `0.497794`, condenser-duty ratio was
`1.034782`, and reflux ratio was `1.002143`; those gates all passed.

This successor therefore establishes that `3.0 MMBTU/h/psi` supplies adequate
pressure authority for the frozen thermal disturbance, but the existing
distillate-composition loop does not keep n-butane within its required band over
the primary horizon. No 600-second checkpoint is accepted and no extension is
authorized. Any composition-gain or integral-time change requires another
separately frozen experiment; it cannot be applied as a retry within this one.

## Composition-gain successor result

Status: **historically stopped at a provisional composition threshold that is now retired; not a product-quality failure**.

The next successor retains the qualified pressure tuning of
`3,000,000 BTU/h/psi` and `Ti = 180 s`. It changes only the distillate n-butane
proportional gain from `5,000` to `30,000 lbmol/h` per mole fraction;
composition `Ti` remains `600 s`. Both level loops, all setpoints, controller
limits, the `0.5 s` timestep, feed boundary, reboiler duty, and every acceptance
gate remain unchanged.

At the strict `0.002` composition-error boundary, the old gain supplies only
`10 lbmol/h` of proportional reflux correction, about `0.17%` of the
`5952.48 lbmol/h` reflux reference. The frozen `30,000` gain supplies
`60 lbmol/h`, approximately `1%` of reference reflux. Holding integral time
fixed isolates proportional authority and avoids combining two tuning changes.

The composition PI memory is back-calculated from saved reflux and the live
n-butane error so the gain change is bumpless; its rate predictor is reconciled
to the new gain. A 60-second unchanged-input qualification must pass before the
same governed `+5 F` disturbance is repeated. The primary and conditional
horizons remain 600 and 1200 seconds, respectively, with the extension allowed
only if every hard gate passes through the primary horizon.

### Higher-gain execution and hard stop

The bumpless composition-gain endpoint passed with reflux movement of only
about `0.0022 lbmol/h`, residual `8.328157e-13`, rank `265/265`, and condition
`4.635319e6`. Its 60-second unchanged-input qualification accepted every
endpoint. Final pressure and composition errors were `-0.0150303 psi` and
`+0.000118194`, the dynamic score was `0.2713`, and reflux remained within
`0.022%` of reference. The qualified dual-retuned checkpoint is:

`logs/core_v3_composition_kc30k_hold60s_20260830/core_v3_checkpoint_20260830_194920.npz`

The repeated disturbed preflight also passed, with residual `1.318975e-12`,
rank `265/265`, condition `4.621441e6`, pressure error `-0.0128900 psi`, and
composition error `+0.000118149`. Its checkpoint is:

`logs/core_v3_kc3m_compkc30k_feedT_plus5F_preflight_20260830/core_v3_checkpoint_20260830_195142.npz`

The continuation passed the earlier `t = 355.0 s` failure point but reached the
same strict composition gate at `t = 372.5 s`. Distillate n-butane error was
`+0.002001712`. Pressure error was only `+0.117186 psi`; drum and sump levels
were `0.501821` and `0.498161`; condenser-duty and reflux ratios were `1.034741`
and `1.012240`; and all actuator and physical gates passed. Numerical closure
also remained strong: residual `7.803185e-13`, rank `265/265`, condition
`4.584860e6`, and controller-memory recurrence error below `1e-18`.

Increasing composition proportional gain sixfold therefore delayed the first
composition violation by only `17.5 s`, from `355.0` to `372.5 s`, despite a
meaningful unsaturated reflux response of about `+1.22%`. This is evidence that
column transport delay dominates the observed overhead composition excursion;
gain authority alone is not an efficient route to the frozen band. The
600-second checkpoint and conditional extension remain unaccepted. A further
gain retry is not authorized by this result. The next useful work should first
characterize the delayed composition peak and turning behavior under a
separately declared diagnostic, or evaluate a feed-forward/alternative-MV
strategy, before freezing another feedback tuning.

## Composition-threshold correction and robustness continuation

No distillate product specification was declared for the `+5 F` experiment.
The former `+/-0.002` n-butane threshold was therefore a provisional response
diagnostic, not a defensible product-quality requirement. The two historical
stops remain useful markers for comparing controller response, but they are no
longer classified as product failures or as reasons to reject an otherwise
physical and numerically sound trajectory.

The Core V3 runner now logs composition without using it as a default stop
condition. A composition limit can still be enforced when a future experiment
declares one explicitly through `--composition-error-limit-molfrac`. The
dual-retuned `+5 F` trajectory is authorized to resume from its retained
recovery checkpoint and continue to the original 600-second horizon as a test
of first-principles model robustness. Numerical, physical, pressure, level,
controller-memory, and manipulated-variable gates remain active.

The resumed trajectory completed the full 600-second disturbance horizon.
Every retained protection passed. At 600 seconds, pressure error was
`+0.00188159 psi`, drum and sump levels were `0.502705` and `0.501203`,
condenser-duty and reflux ratios were `1.031551` and `1.027108`, and the final
endpoint remained physical with residual `4.752459e-13`, rank `265/265`,
condition `4.596800e6`, and controller-memory recurrence error
`3.354250e-18`. No solve coordinate was at a bound.

Distillate n-butane reached `0.123656477` mole fraction, or
`+0.003784725` above its controller setpoint. It was still increasing at the
600-second endpoint, although its sampled rate of increase had begun to
decline. This is a composition-response observation, not a product failure.
The model remained bounded and the final steady-state score was `0.955390`
with the steady-state flag asserted. The completed native checkpoint is:

`logs/core_v3_kc3m_compkc30k_feedT_plus5F_complete600s_20260830/core_v3_checkpoint_20260830_204510.npz`

The extended tuning comparison chart is:

`logs/core_v3_composition_tuning_comparison_20260830/distillate_xc4_comparison.png`
