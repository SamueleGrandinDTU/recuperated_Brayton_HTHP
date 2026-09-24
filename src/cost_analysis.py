"""Component cost estimation for the standalone base recuperated HTHP.

Compressors and turbines are costed with the Turton et al. (2001) correlation;
heat exchangers are costed with the Morandin correlation. Both defaults are
printed to the console every time the function runs, since which correlation
(and which heat-transfer coefficients) were used materially affects the
result.
"""

import math

import pandas as pd

from src import save_table_as_csv, save_table_as_png

# Turton correlation coefficients: Cp0 = 10^(K1 + K2*log10(P) + K3*log10(P)^2),
# P in kW. C_BM = Cp0 * F_BM. "limits" are the correlation's validated power
# range in kW.
# "limits" for Tank are validated volume range in m³, not power.
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


def calculate_component_cost(
    plant,
    external_components=None,
    I_current=800,
    title_name=None,
    file_name=None,
    save_path=None,
):
    """Estimate and print the cost of the plant's compressors, turbines and
    heat exchangers, plus any TES tanks passed in separately.

    Compressor/turbine cost basis: power [kW], Turton et al. (2001)
    correlation, actualized from the 2001 cost index to the current one.
    Heat exchanger cost basis: heat transfer area [m²] (back-calculated from
    kA and an assumed overall heat transfer coefficient U), Morandin
    correlation, actualized from the 2009 cost index to the current one.
    Tank cost basis: volume [m³] (from `geometry.calculate_tanks_geometry`),
    Turton et al. (2001) correlation, actualized the same way as
    compressors/turbines.

    Tanks aren't part of the TESPy network, so they can't be discovered from
    `plant.comps["object"]` the way compressors/turbines/heat exchangers are;
    they're passed in explicitly via `external_components`.

    The cost indexes for each correlation's reference year (_COST_INDEX_REFERENCE)
    and the heat exchanger U values (_HX_U_VALUES) are fixed module-level
    constants, same as the Turton coefficients, rather than function inputs.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    external_components : list, optional
        Components that aren't part of the TESPy network but should still be
        costed, e.g. the Tank objects returned by
        `geometry.calculate_tanks_geometry`. Only Tank objects are costed;
        anything else in the list is ignored.
    I_current : float, optional
        Current cost index (CEPCI). Default 800 (2025).
    title_name : str, optional
        Title used for the saved PNG table. If None, no PNG is generated.
    file_name : str, optional
        Base file name used when saving the table (characteristic extension
        is added).
    save_path : str or Path, optional
        Directory to save the table as CSV / PNG files.
        If None, nothing is saved to disk. The saved table is a simplified
        (Component, Cost [M€]) view with a final "Total" row, distinct from
        the full (Component, Type, Basis parameter, Basis value, Cost [M€])
        table this function returns.

    Returns
    -------
    df_cost : pd.DataFrame
        Component cost table (Component, Type, Basis parameter, Basis value, Cost [M€]).
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
    print("Heat exchanger cost correlation: Morandin")
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
            cost = C_BM * I_current / _COST_INDEX_REFERENCE["Turton"]
            cost_M = (cost / 1e6) * _USD_TO_EUR

            rows.append(
                {
                    "Component": comp.label,
                    "Type": comp_type,
                    "Basis parameter": "Power [kW]",
                    "Basis value": round(P_kW, 1),
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
            cost = C_BM * I_current / _COST_INDEX_REFERENCE["Morandin"]
            cost_M = (cost / 1e6) * _USD_TO_EUR

            rows.append(
                {
                    "Component": comp.label,
                    "Type": comp_type,
                    "Basis parameter": "Area [m²]",
                    "Basis value": round(area, 2),
                    "Cost [M€]": round(cost_M, 3),
                }
            )

    for comp in external_components or []:
        if comp.__class__.__name__ != "Tank":
            continue

        coeffs = _TURTON_COEFFS["Tank"]
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
        cost = C_BM * I_current / _COST_INDEX_REFERENCE["Turton"]
        cost_M = (cost / 1e6) * _USD_TO_EUR

        rows.append(
            {
                "Component": comp.label,
                "Type": "Tank",
                "Basis parameter": "Volume [m³]",
                "Basis value": round(V_m3, 1),
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

    if save_path is not None:
        if file_name is None:
            raise ValueError("file_name is required when save_path is given.")

        header = ["Component", "Cost [M€]"]
        data_rows = df_cost[header].values.tolist()
        total_row = ["total", round(total_cost, 3)]
        df_cost_save = pd.DataFrame([header] + data_rows + [total_row])

        save_table_as_csv(df_cost_save, save_path, f"{file_name}_components_cost")

        if title_name is not None:
            save_table_as_png(
                df_cost_save,
                f"{title_name} - Components Cost",
                save_path,
                f"{file_name}_components_cost",
            )

    return df_cost
