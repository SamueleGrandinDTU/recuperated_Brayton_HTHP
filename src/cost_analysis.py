"""Component cost estimation for the standalone base recuperated HTHP.

Compressors and turbines are costed with the Turton et al. (2001) correlation;
heat exchangers are costed with the Morandin correlation. Both defaults are
printed to the console every time the function runs, since which correlation
(and which heat-transfer coefficients) were used materially affects the
result.
"""

import math

import pandas as pd

# Turton correlation coefficients: Cp0 = 10^(K1 + K2*log10(P) + K3*log10(P)^2),
# P in kW. C_BM = Cp0 * F_BM. "limits" are the correlation's validated power
# range in kW.
_TURTON_COEFFS = {
    "Compressor": {
        "K1": 2.2897,
        "K2": 1.3604,
        "K3": -0.1027,
        "F_BM": 3.8,
        "limits": (450, 3000),
    },
    "Turbine": {
        "K1": 2.7051,
        "K2": 1.4398,
        "K3": -0.1776,
        "F_BM": 3.4,
        "limits": (100, 4000),
    },
    "Tank": {
        "K1": 4.8509,
        "K2": -0.3973,
        "K3": 0.1445,
        "F_BM": 1,
        "limits": (90, 30000),
    },
}

# Cost indexes for the reference year of each correlation (CEPCI-style).
_COST_INDEX_REFERENCE = {
    "Turton": 394,  # 2001
    "Morandin": 522,  # 2009
    "2025": 800,  # Current cost index (CEPCI)
}

# Overall heat transfer coefficients [W/m²K] used to back out the heat
# transfer area for each heat exchanger type, keyed by the label match used
# to identify it (see calculate_component_cost).
_HX_U_VALUES = {
    "sink": 70,  # gas-to-liquid, 1 bar
    "recuperator": 35,  # gas-to-gas, shell-and-tube, 1 bar
}

# The Turton/Morandin correlations return costs in $; convert to € here so
# the console table, the returned DataFrame, and any plot built from it all
# agree on the currency.
_USD_TO_EUR = 0.92


def calculate_component_cost(plant):
    """Estimate and print the cost of the plant's compressors, turbines and
    heat exchangers.

    Compressor/turbine cost basis: power [kW], Turton et al. (2001)
    correlation, actualized from the 2001 cost index to the current one.
    Heat exchanger cost basis: heat transfer area [m²] (back-calculated from
    kA and an assumed overall heat transfer coefficient U), Morandin
    correlation, actualized from the 2009 cost index to the current one.

    The cost indexes for each correlation's reference year (_COST_INDEX_REFERENCE)
    and the heat exchanger U values (_HX_U_VALUES) are fixed module-level
    constants, same as the Turton coefficients, rather than function inputs.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    I_current : float, optional
        Current cost index (CEPCI). Default 800 (2025).

    Returns
    -------
    df_cost : pd.DataFrame
        Component cost table (Component, Type, Basis parameter, Basis value, Cost [M$]).
    """
    print(f"\n{'=' * 100}")
    print("COMPONENT COST ESTIMATION")
    print(f"{'=' * 100}")
    print("Turbomachinery and tank cost correlation: Turton et al. (2001)")
    print(
        f"  Compressor validity range: {_TURTON_COEFFS['Compressor']['limits'][0]}-{_TURTON_COEFFS['Compressor']['limits'][1]} kW"
    )
    print(
        f"  Turbine validity range: {_TURTON_COEFFS['Turbine']['limits'][0]}-{_TURTON_COEFFS['Turbine']['limits'][1]} kW"
    )
    print(
        f"  Tank validity range: {_TURTON_COEFFS['Tank']['limits'][0]}-{_TURTON_COEFFS['Tank']['limits'][1]} m³"
    )
    print("Heat exchanger cost correlation: Morandin et al. (2009)")
    print(
        f"  Recuperator-type HX: gas-to-gas, shell-and-tube, 1 bar, "
        f"U = {_HX_U_VALUES['recuperator']} W/m²K"
    )
    print(f"  Sink-type HX: gas-to-liquid, 1 bar, U = {_HX_U_VALUES['sink']} W/m²K")

    rows = []

    for comp in plant.comps["object"]:
        comp_type = comp.__class__.__name__

        if comp_type in ("Compressor", "Turbine"):
            coeffs = _TURTON_COEFFS[comp_type]
            P_kW = abs(comp.P.val) * 1000

            lower, upper = coeffs["limits"]
            if not (lower <= P_kW <= upper):
                print(
                    f"Error: {comp.label} power ({round(P_kW, 1)} kW) is outside "
                    f"the Turton correlation validity range ({lower}-{upper} kW). "
                    "The cost below is extrapolated and may not be reliable."
                )

            log_P = math.log10(P_kW)
            C_p0 = 10 ** (coeffs["K1"] + coeffs["K2"] * log_P + coeffs["K3"] * log_P**2)
            C_BM = C_p0 * coeffs["F_BM"]
            cost = (
                C_BM * _COST_INDEX_REFERENCE["2025"] / _COST_INDEX_REFERENCE["Turton"]
            )
            cost_M = cost / 1e6 * _USD_TO_EUR

            rows.append(
                {
                    "Component": comp.label,
                    "Type": comp_type,
                    "Basis parameter": "Power [kW]",
                    "Basis value": round(P_kW, 1),
                    "Cost [M€]": round(cost_M, 3),
                }
            )

        if comp_type in ("Tank"):
            coeffs = _TURTON_COEFFS[comp_type]
            V_m3 = abs(comp.V.val)

            lower, upper = coeffs["limits"]
            if not (lower <= V_m3 <= upper):
                print(
                    f"Error: {comp.label} volume ({round(V_m3, 1)} m³) is outside "
                    f"the Turton correlation validity range ({lower}-{upper} m³). "
                    "The cost below is extrapolated and may not be reliable."
                )

            log_V = math.log10(V_m3)
            C_p0 = 10 ** (coeffs["K1"] + coeffs["K2"] * log_V + coeffs["K3"] * log_V**2)
            C_BM = C_p0 * coeffs["F_BM"]
            cost = (
                C_BM * _COST_INDEX_REFERENCE["2025"] / _COST_INDEX_REFERENCE["Turton"]
            )
            cost_M = cost / 1e6 * _USD_TO_EUR

            rows.append(
                {
                    "Component": comp.label,
                    "Type": comp_type,
                    "Basis parameter": "Volume [m³]",
                    "Basis value": round(V_m3, 1),
                    "Cost [M€]": round(cost_M, 3),
                }
            )

        elif comp_type == "HeatExchanger":
            U = (
                _HX_U_VALUES["sink"]
                if "sink" in str(comp.label).lower()
                else _HX_U_VALUES["recuperator"]
            )
            area = comp.kA.val / U

            C_BM = 5000 + 450 * area**0.82
            cost = (
                C_BM * _COST_INDEX_REFERENCE["2025"] / _COST_INDEX_REFERENCE["Morandin"]
            )
            cost_M = cost / 1e6 * _USD_TO_EUR

            rows.append(
                {
                    "Component": comp.label,
                    "Type": comp_type,
                    "Basis parameter": "Area [m²]",
                    "Basis value": round(area, 2),
                    "Cost [M€]": round(cost_M, 3),
                }
            )

    df_cost = pd.DataFrame(rows)
    total_cost = df_cost["Cost [M€]"].sum()

    print(f"{'=' * 100}")
    print("COMPONENT COSTS")
    print(f"{'=' * 100}")
    print(df_cost.to_string(index=False))
    print(f"{'=' * 100}")
    print(f"Total plant cost: {round(total_cost, 3)} M€")
    print(f"{'=' * 100}")

    return df_cost
