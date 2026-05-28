#!/usr/bin/env python
"""
Create a ChemSep .sep starter case for the Gani et al. 1986 debutanizer.

The file is intentionally a steady-state reconciliation template. It uses the
user-provided Depropanizer.sep conventions and ChemSep's local component
database records, then fills in the Gani Problem II components, feed,
pressure profile, reflux flow, and reboiler duty.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


CHEMSEP_ROOT = Path(r"C:\Users\Thoma\AppData\Local\ChemSepL8v42")
OUT_PATH = CHEMSEP_ROOT / "Gani_1986_Debutanizer_PR.sep"
PROJECT_COPY = Path(__file__).resolve().parents[1] / "logs" / "Gani_1986_Debutanizer_PR.sep"

KMOLH_TO_KMOLS = 1.0 / 3600.0
KPA_TO_PA = 1000.0
K_TO_C_OFFSET = 273.15
GCAL_PER_H_TO_MW = 4.184e9 / 3600.0 / 1.0e6


def _fmt(x: float) -> str:
    return f"{float(x):.10g}"


def build_text() -> str:
    # ChemSep pure-component metadata from the local chemsep1.xml and examples.
    # The first number is the library offset/ordinal; the second is ChemSep's
    # library index. CHK values for components not present in local example
    # files are left as 0; ChemSep can refresh these when the case is opened.
    components = [
        (77, 303, 0, "106-99-0", "1,3-butadiene"),
        (81, 207, -90782246, "115-11-7", "Isobutene"),
        (115, 7, 188892023, "109-66-0", "N-pentane"),
        (108, 209, 0, "109-67-1", "1-pentene"),
        (130, 216, 0, "592-41-6", "1-hexene"),
        (125, 501, 63532870, "71-43-2", "Benzene"),
    ]

    n_stages = 28
    feed_stage = 23
    # ChemSep stores flow values as kmol/s even when the UI presents molar
    # flow in selected display units such as lbmol/h.
    feed_total_kmols = (236.86 + 266.18) * KMOLH_TO_KMOLS
    feed_z = [0.23791, 0.30817, 0.09959, 0.13727, 0.08872, 0.12834]
    z_sum = sum(feed_z)
    feed_z = [v / z_sum for v in feed_z]
    feed_component_kmols = [feed_total_kmols * z for z in feed_z]

    top_p_pa = 527.50 * KPA_TO_PA
    bottom_p_pa = 555.30 * KPA_TO_PA
    feed_p_pa = top_p_pa + (bottom_p_pa - top_p_pa) * ((feed_stage - 1) / (n_stages - 1))
    feed_t_k = 338.0

    reflux_kmols = 429.8 * KMOLH_TO_KMOLS
    reboiler_duty_mw = 2.760 * GCAL_PER_H_TO_MW

    now = datetime.now()
    lines: list[str] = []
    lines.extend(
        [
            "[ChemSep]",
            "Version=8.00",
            "Compiled=2018-10-24 14:13 568458edfde8",
            "Name=Gani_1986_Debutanizer_PR.sep",
            "Title=Gani Ruiz Cameron 1986 Problem II industrial debutanizer PR starter",
            "User=Codex",
            f"Date={now:%Y-%m-%d}",
            f"Time={now:%H:%M:%S}",
            "",
            "[Paths]",
            f"Device drivers path={CHEMSEP_ROOT / 'bin'}\\",
            f"Help and Info path={CHEMSEP_ROOT / 'help'}\\",
            f"Component data path={CHEMSEP_ROOT / 'pcd'}\\",
            f"Property data path={CHEMSEP_ROOT / 'ipd'}\\",
            f"Section data path={CHEMSEP_ROOT / 'ild'}\\",
            f"Executables path={CHEMSEP_ROOT / 'bin'}\\",
            f"Temporary path={CHEMSEP_ROOT / 'tmp'}\\",
            f"Scripts path={CHEMSEP_ROOT / 'bin'}\\",
            "",
            "[Units]",
            "Temperature=C",
            "Flow=mol/s",
            "Mass flow=kg/s",
            "Vapour volumetric flow=m3/s",
            "Liquid volumetric flow=m3/s",
            "Pressure=Pa",
            "Heat=MW",
            "Enthalpy=kJ/kmol",
            "Entropy=J/kmol/K",
            "Fraction=_",
            "Length=m",
            "1/Length=1/m",
            "Area=m2",
            "Volume=m3",
            "Moles=kmol",
            "Mass=kg",
            "Angle=rad",
            "Velocity=m/s",
            "Surface tension=N/m",
            "Density=kg/m3",
            "Molar density=kmol/m3",
            "Viscosity=N/m2.s",
            "Molecular weight=kg/kmol",
            "Heat capacity=J/kmol/K",
            "Thermal conductivity=J/s/m/K",
            "Diffusivity=1e-8 m2/s",
            "Interaction parameter=J/mol",
            "Time=s",
            "",
            "[Components]",
            f"{len(components)} Number of Components",
        ]
    )
    for offset, index, chk, cas, name in components:
        lines.append(
            f"{offset} {index} Library Offset, Index DT=2018-10-24,04:46:32 CHK={chk} CAS={cas} CID={name}"
        )
        lines.append(f"Name={name}")
        lines.append(f"Lib={CHEMSEP_ROOT}\\pcd\\chemsep1.pcd")

    lines.extend(
        [
            "",
            "[Operation]",
            "2 Operation Column",
            "1 Operation kind Simple Distillation",
            "1 Condenser Total (Liquid product)",
            "1 Reboiler Partial (Liquid product)",
            f"{n_stages} Stages",
            "1 Feed stages",
            "0 Sidestream stages",
            f"F={feed_stage}",
            "S=",
            "0 Pumparound stages",
            "P=",
            "0 Interconnections",
            "I=",
            "",
            "[Simulation Model]",
            "*  Simulation model *",
            "",
            "[Properties]",
            "350 BIP estimation temperature",
            "0 Estimation BIPs",
            "",
            "[Thermodynamics]",
            "2 K model EOS",
            "* * Activity coefficient *",
            "*  Wilson model *",
            "*  UNIQUAC model *",
            "3 Equation of State Cubic",
            "5 Cubic EOS Peng-Robinson 76",
            "*  Virial EOS *",
            "*  Vapour pressure *",
            "0 Henry's law",
            "*  Henry's default *",
            "",
            "[Enthalpy]",
            "3 Enthalpy Excess",
            "1 Enthalpy reference state Vapour",
            "298.15 Enthalpy reference temperature",
            "1 Formation enthalpies Excluded",
            "298.15 Exergy surroundings temperature",
            "",
            "[Physical property models]",
            "0 1 No Check T range",
            "*  Cubic EOS *",
            "*  Virial EOS *",
            "*  Vapour model *",
            "*  Liquid mixture density *",
            "*  Liquid component density *",
            "*  Vapour mixture viscosity *",
            "*  Vapour mixture viscosity pressure correction *",
            "*  Vapour component viscosity *",
            "*  Liquid mixture viscosity *",
            "*  Liquid component viscosity *",
            "* Vapour mixture Cp",
            "2 Vapour component Cp 4th order polynomial (Reid-Prausnitz-Poling)",
            "*  Liquid mixture Cp *",
            "* Liquid component Cp",
            "*  Vapour mixture conductivity *",
            "*  Vapour component conductivity *",
            "*  Liquid mixture conductivity *",
            "*  Liquid component conductivity *",
            "*  Mixture surface tension *",
            "*  Component surface tension *",
            "*  Vignes MS D-model *",
            "*  D mixture model *",
            "*  Vapour Diffusion Coefficients *",
            "12 Default Liquid Diffusion Coefficients Kooijman",
            "*  Interfacial tension *",
            "",
            "[Property Data]",
            "",
            "[Peng-Robinson 76 Data]",
            "      i      j          kij  Component Component",
            "",
            "[Reaction data]",
            "0 Number of reactions",
            "",
            "[Specifications]",
            "Top",
            "Bottom",
            "",
            "[Heaters/Coolers]",
            "0 Number",
            "0 Column duty Qcolumn",
            "2 First stage",
            f"{n_stages - 1} Last stage",
            "0 Qcolumn lost to surroundings",
            "",
            "[Efficiencies]",
            "1 Default efficiency",
            "0 Number",
            "",
            "[Pressures]",
            "2 Column pressure Bottom & top pressures",
            f"{_fmt(top_p_pa)} Condenser pressure",
            f"{_fmt(top_p_pa)} Top pressure",
            "* Pressure Drop",
            f"{_fmt(bottom_p_pa)} Bottom pressure",
            "",
            "[Feeds]",
            "1 Number",
            "1 Feed state T & p",
            f"{feed_stage} Stage Feed1{{split}}",
            f"{_fmt(feed_t_k)} Temperature",
            f"{_fmt(feed_p_pa)} Pressure",
            "0.138021358 Vapour fraction",
            f"{len(components)} componentflows",
        ]
    )
    for idx, flow in enumerate(feed_component_kmols, start=1):
        lines.append(f"{_fmt(flow)} Component {idx} flow")

    lines.extend(
        [
            "",
            "[Condenser]",
            "5 Type Reflux flow rate",
            f"{_fmt(reflux_kmols)} Value Qcondenser",
            "*  Type *",
            "* Initialization guess",
            "",
            "[Reboiler]",
            "2 Type Heat duty of reboiler",
            f"{_fmt(reboiler_duty_mw)} Value Qreboiler",
            "*  Type *",
            "* Initialization guess",
            "",
            "[Monitored Variables]",
            "*",
            "",
            "",
            "[Solve options]",
            "1 Initialization Automatic",
            "1 Method Newton's method",
            "0.5 Flow Step limit",
            "10 Temperature Step limit",
            "1 Composition Step limit",
            "1 Flux Step limit",
            "0.000001 Accuracy",
            "30 Maximum iterations",
            "1 Iteration count & function vector",
            "0 T/V/L profiles",
            "0 X/Y profiles",
            "0 Variable and function vectors",
            "0 Jacobian",
            "1 History Screen",
            "History file=",
            "1 Feeds type Stage below",
            "0 Interactive",
            "0 Log thermodynamics",
            "0 Log enthalpy/entropy",
            "0 Log physical properties",
            "0 Log timing",
            "0 CO numeric differencing",
            "* Log from iteration",
            "0 CS K-value",
            "0 CS enthalpy",
            "0 CS entropy",
            "0 CS flash",
            "0 CS activity coefficient",
            "0 CS vapor pressuure",
            "0 CS density",
            "0 CS viscosity",
            "0 CS thermal conductivity",
            "0 CS heat capacity",
            "0 CS surface tension",
            "0 CS diffusivity",
            "0 Trace treshold",
            "",
            "[End of Results]",
            "",
            "[ChemSep Output]",
            "",
            "[End ChemSep Output]",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    text = build_text()
    text = text.replace("\n", "\r\n")
    OUT_PATH.write_text(text, encoding="utf-8", newline="")
    PROJECT_COPY.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_COPY.write_text(text, encoding="utf-8", newline="")
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {PROJECT_COPY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
