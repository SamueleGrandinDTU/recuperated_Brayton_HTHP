"""Exergy analysis post-processing.
============================================================
This modules calculates connection exergy, component exergy balance,
exergetic efficiency, cycle exergy efficiency and total exergy destruction logic.
"""

import pandas as pd
from CoolProp.CoolProp import PropsSI


def get_exergy_analysis(plant, T_0=None, p_0=None):
    """Run the full exergy analysis for a solved plant.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    T_0 : float, optional
        Ambient temperature [°C]. If not given, taken from connection "0";
        if connection "0" does not exist, defaults to 15 °C.
    p_0 : float, optional
        Ambient pressure [bar]. If not given, taken from connection "0";
        if connection "0" does not exist, defaults to 1 bar.

    Returns
    -------
    dict
        {
            "connections": df_connections,
            "components": df_components,
            "efficiencies": df_efficiencies,
            "exergy_conn": exergy_conn,
            "cycle_exergy_efficiency": cycle_exergy_eff,
            "total_exergy_destruction": total_exergy_destruction,
        }
    """
    T_0, p_0 = _get_ambient_conditions(plant, T_0, p_0)

    # Get reference state values
    fluid = _get_fluid(plant)
    h0, s0 = _get_reference_state(T_0, p_0, fluid)

    # Calculate connection exergy (air connections only)
    df_connections, exergy_conn = _calculate_connection_exergy(plant, T_0, h0, s0)

    # Calculate component exergy balance
    df_components = _calculate_component_exergy(plant, plant, T_0)

    # Calculate exergetic efficiencies
    df_efficiencies = _calculate_exergetic_efficiencies(df_components)

    # Calculate cycle exergy efficiency
    cycle_ex_eff = _calculate_cycle_exergy_efficiency(plant, df_components)

    # Calculate total exergy destruction
    cycle_Ex_D = _calculate_total_exergy_destruction(df_components)

    # ------------------------------------------------------------------
    # Console display
    # ------------------------------------------------------------------

    # 1. Connection exergy values, with the reference state made explicit
    print(f"\n{'=' * 100}")
    print("CONNECTION EXERGY VALUES")
    print(f"{'=' * 100}")
    print(f"Reference state: T_0 = {T_0} °C, p_0 = {p_0} bar, fluid = {fluid}")
    print(f"h_0 = {h0} kJ/kg, s_0 = {s0} kJ/(kg·K)")
    print(f"{'=' * 100}")
    print(df_connections.to_string(index=False))
    print(f"{'=' * 100}")

    # 2. Component table: Component, Ex_P, Ex_F, Ex_D, ex_eff
    df_display = df_components.merge(
        df_efficiencies[["Component", "ex_eff"]], on="Component"
    )
    df_display = df_display[
        ["Component", "Ex_P [MW]", "Ex_F [MW]", "Ex_D [MW]", "ex_eff"]
    ]
    df_display["ex_eff"] = (df_display["ex_eff"] * 100).round(2)
    df_display = df_display.rename(columns={"ex_eff": "ex_eff [%]"})

    print(f"\n{'=' * 100}")
    print("COMPONENT EXERGY BALANCE")
    print(f"{'=' * 100}")
    print(df_display.to_string(index=False))
    print(f"{'=' * 100}")

    # 3. Cycle-level exergy performance
    print(f"\n{'=' * 100}")
    print("CYCLE EXERGY PERFORMANCE")
    print(f"{'=' * 100}")
    print(f"Cycle exergy efficiency (cycle_ex_eff): {cycle_ex_eff*100} %")
    print(f"Total exergy destruction (cycle_Ex_D): {cycle_Ex_D} MW")
    print(f"{'=' * 100}")

    return {
        "connections": df_connections,
        "components": df_components,
        "efficiencies": df_efficiencies,
        "exergy_conn": exergy_conn,
        "cycle_ex_eff": cycle_ex_eff,
        "cycle_Ex_D": cycle_Ex_D,
    }


def _get_ambient_conditions(plant, T_0, p_0):
    """Resolve ambient T_0 [°C] / p_0 [bar], falling back to connection "0".

    If T_0 / p_0 are not given, they are taken from connection "0"; if that
    connection does not exist, they default to 15 °C and 1 bar.
    """
    conn_0 = None
    for conn in plant.conns["object"]:
        if str(conn.label) == "0":
            conn_0 = conn
            break

    if T_0 is None:
        T_0 = conn_0.T.val if conn_0 is not None else 15.0

    if p_0 is None:
        p_0 = conn_0.p.val if conn_0 is not None else 1.0

    return T_0, p_0


def _get_fluid(plant):
    """Determine the plant's main working fluid from its connections."""
    for conn in plant.conns["object"]:
        fluid_val = conn.fluid.val
        if fluid_val:
            return max(fluid_val, key=fluid_val.get)
    return "air"


def _get_reference_state(T_0, p_0, fluid):
    """Calculate reference state enthalpy and entropy with a fallback to Air

    if the fluid is not computable.
    """
    try:
        # Attempt to calculate with the provided fluid
        h0 = PropsSI("H", "T", T_0 + 273.15, "P", p_0 * 1e5, fluid) / 1000
        s0 = PropsSI("S", "T", T_0 + 273.15, "P", p_0 * 1e5, fluid) / 1000  # kJ/(kg·K)
    except Exception:
        # Fallback to "Air" if the specified fluid fails or is not computable
        h0 = PropsSI("H", "T", T_0 + 273.15, "P", p_0 * 1e5, "Air") / 1000
        s0 = PropsSI("S", "T", T_0 + 273.15, "P", p_0 * 1e5, "Air") / 1000

    return round(h0, 2), round(s0, 2)


def _calculate_connection_exergy(plant, T_0, h0, s0):
    """Calculate specific exergy and exergy flow for air connections only."""
    data_exergy = []
    exergy_conn = {}

    for conn in plant.conns["object"]:
        if conn.h.val is None or conn.s.val is None or conn.m.val is None:
            continue

        # Check if connection is air only
        fluids_in_conn = list(conn.fluid.val.keys())
        if len(fluids_in_conn) != 1 or fluids_in_conn[0] != "air":
            exergy_conn[conn.label] = None
            continue

        h = conn.h.val
        s = conn.s.val
        m = conn.m.val

        # Specific exergy (kJ/kg)
        ex = (h - h0) - (T_0 + 273.15) * (s - s0)
        # Exergy flow (MW)
        Ex = m * ex / 1000

        exergy_conn[conn.label] = Ex

        # Skip connection labeled "0" if it exists
        data_exergy.append(
            {
                "Connection": conn.label,
                "ex [kJ/kg]": round(ex, 2),
                "Ex [MW]": round(Ex, 2),
            }
        )

    df = pd.DataFrame(data_exergy)
    return df, exergy_conn


def _calculate_component_exergy(plant, plant_ref, T_0):
    """Calculate exergy balance for turbines, compressors, and heat exchangers."""
    data_components = []

    for comp in plant.comps["object"]:
        comp_type = comp.__class__.__name__

        if comp_type == "Turbine":
            result = _process_turbine(comp, plant_ref, T_0)
            if result:
                data_components.append(result)

        elif comp_type == "Compressor":
            result = _process_compressor(comp, plant_ref, T_0)
            if result:
                data_components.append(result)

        elif comp_type == "HeatExchanger":
            result = _process_heat_exchanger(comp, plant_ref, T_0)
            if result:
                data_components.append(result)

    df = pd.DataFrame(data_components)
    return df


def _get_component_connections(comp, plant):
    """
    Map component inlet/outlet to cycle point (connection) labels.
    Maintains correct order: in1, in2, ... and out1, out2, ...
    """
    inlet_conns = []
    outlet_conns = []

    for _, conn_obj in plant.conns.iterrows():
        conn = conn_obj["object"]

        if hasattr(conn, "source") and conn.source is comp:
            port_num = int("".join(filter(str.isdigit, conn.source_id)))
            outlet_conns.append((port_num, conn.label))

        if hasattr(conn, "target") and conn.target is comp:
            port_num = int("".join(filter(str.isdigit, conn.target_id)))
            inlet_conns.append((port_num, conn.label))

    inlet_labels = [label for _, label in sorted(inlet_conns)]
    outlet_labels = [label for _, label in sorted(outlet_conns)]

    return inlet_labels, outlet_labels


def _get_connection_by_label(plant, label):

    for conn in plant.conns["object"]:
        if conn.label == label:
            return conn
    return None


def _calculate_exergy_from_connection(conn, T_0):

    if conn is None or conn.m.val is None or conn.h.val is None or conn.s.val is None:
        return None
    return conn.m.val * (conn.h.val - (T_0 + 273.15) * conn.s.val) / 1000  # MW


def _process_turbine(comp, plant, T_0):
    """Process turbine: E_F = E_in - E_out, E_P = W_tu"""
    try:
        inlet_labels, outlet_labels = _get_component_connections(comp, plant)

        if not inlet_labels or not outlet_labels:
            print(f"Warning: Turbine '{comp.label}' has no inlet or outlet connections")
            return None

        # Calculate inlet and outlet exergy
        E_in = sum(
            _calculate_exergy_from_connection(
                _get_connection_by_label(plant, label), T_0
            )
            for label in inlet_labels
        )
        E_out = sum(
            _calculate_exergy_from_connection(
                _get_connection_by_label(plant, label), T_0
            )
            for label in outlet_labels
        )

        if E_in is None or E_out is None:
            print(
                f"Warning: Turbine '{comp.label}' could not calculate inlet/outlet exergy"
            )
            return None

        if not hasattr(comp, "P") or comp.P.val is None:
            print(f"Warning: Turbine '{comp.label}' has no power value")
            return None

        W_tu = comp.P.val

        E_F = E_in - E_out
        E_P = abs(W_tu)
        E_D = E_F - E_P

        return {
            "Component": comp.label,
            "Type": "Turbine",
            "Ex_F [MW]": round(E_F, 3),
            "Ex_P [MW]": round(E_P, 3),
            "Ex_D [MW]": round(E_D, 3),
        }
    except Exception as e:
        print(f"Error processing turbine '{comp.label}': {e}")
        return None


def _process_compressor(comp, plant, T_0):
    """Process compressor: E_F = W_cp, E_P = E_out - E_in"""
    try:
        inlet_labels, outlet_labels = _get_component_connections(comp, plant)

        if not inlet_labels or not outlet_labels:
            print(
                f"Warning: Compressor '{comp.label}' has no inlet or outlet connections"
            )
            return None

        # Calculate inlet and outlet exergy
        E_in = sum(
            _calculate_exergy_from_connection(
                _get_connection_by_label(plant, label), T_0
            )
            for label in inlet_labels
        )
        E_out = sum(
            _calculate_exergy_from_connection(
                _get_connection_by_label(plant, label), T_0
            )
            for label in outlet_labels
        )

        if E_in is None or E_out is None:
            print(
                f"Warning: Compressor '{comp.label}' could not calculate inlet/outlet exergy"
            )
            return None

        if not hasattr(comp, "P") or comp.P.val is None:
            print(f"Warning: Compressor '{comp.label}' has no power value")
            return None

        W_cp = comp.P.val

        E_F = abs(W_cp)
        E_P = E_out - E_in
        E_D = E_F - E_P

        return {
            "Component": comp.label,
            "Type": "Compressor",
            "Ex_F [MW]": round(E_F, 3),
            "Ex_P [MW]": round(E_P, 3),
            "Ex_D [MW]": round(E_D, 3),
        }
    except Exception as e:
        print(f"Error processing compressor '{comp.label}': {e}")
        return None


def _process_heat_exchanger(comp, plant, T_0):
    """Process heat exchanger: E_F = E_hot_in - E_hot_out, E_P = E_cold_out - E_cold_in"""
    try:
        inlet_labels, outlet_labels = _get_component_connections(comp, plant)

        if len(inlet_labels) < 2 or len(outlet_labels) < 2:
            print(
                f"Warning: Heat Exchanger '{comp.label}' does not have 2 inlets and 2 outlets"
            )
            return None

        # Hot side (inlets[0], outlets[0]), Cold side (inlets[1], outlets[1])
        E_hot_in = _calculate_exergy_from_connection(
            _get_connection_by_label(plant, inlet_labels[0]), T_0
        )
        E_hot_out = _calculate_exergy_from_connection(
            _get_connection_by_label(plant, outlet_labels[0]), T_0
        )
        E_cold_in = _calculate_exergy_from_connection(
            _get_connection_by_label(plant, inlet_labels[1]), T_0
        )
        E_cold_out = _calculate_exergy_from_connection(
            _get_connection_by_label(plant, outlet_labels[1]), T_0
        )

        if any(x is None for x in [E_hot_in, E_hot_out, E_cold_in, E_cold_out]):
            print(
                f"Warning: Heat Exchanger '{comp.label}' could not calculate inlet/outlet exergy"
            )
            return None

        E_F = E_hot_in - E_hot_out
        E_P = E_cold_out - E_cold_in
        E_D = E_F - E_P

        return {
            "Component": comp.label,
            "Type": "Heat Exchanger",
            "Ex_F [MW]": round(E_F, 3),
            "Ex_P [MW]": round(E_P, 3),
            "Ex_D [MW]": round(E_D, 3),
        }
    except Exception as e:
        print(f"Error processing heat exchanger '{comp.label}': {e}")
        return None


def _calculate_exergetic_efficiencies(df_components):
    """Calculate exergetic efficiency ex_eff = Ex_P / Ex_F for each component."""
    if df_components.empty:
        print("Warning: No components found for exergy analysis")
        return pd.DataFrame(columns=["Component", "Type", "ex_eff"])

    df = df_components.copy()

    df["ex_eff"] = df.apply(
        lambda row: (
            round(row["Ex_P [MW]"] / row["Ex_F [MW]"], 3)
            if row["Ex_F [MW]"] != 0
            else 0
        ),
        axis=1,
    )

    return df[["Component", "Type", "ex_eff"]]


def _calculate_cycle_exergy_efficiency(plant, df_components):
    """
    Calculate overall cycle exergy efficiency.

    cycle_ex_eff = Ex_P (useful output) / |Net Power|

    The useful output is the "interface hx" component's Ex_P when that
    component is present; otherwise it is the sum of Ex_P over all heat
    exchangers labeled "sink" (covering "sink", "sink 1", "sink 2", etc.).
    """
    he_rows = df_components[df_components["Type"] == "Heat Exchanger"]

    interface_rows = he_rows[
        he_rows["Component"].str.lower().str.contains("interface hx")
    ]

    if not interface_rows.empty:
        ex_p_total = interface_rows["Ex_P [MW]"].sum()
    else:
        sink_rows = he_rows[he_rows["Component"].str.lower().str.contains("sink")]

        if sink_rows.empty:
            print(
                "Warning: No interface hx or sink heat exchangers found for "
                "cycle efficiency calculation"
            )
            return 0.0

        ex_p_total = sink_rows["Ex_P [MW]"].sum()

    # Calculate net power from all turbines and compressors
    net_power = 0.0
    for comp in plant.comps["object"]:
        comp_type = comp.__class__.__name__
        if comp_type in ["Turbine", "Compressor"]:
            if hasattr(comp, "P") and comp.P.val is not None:
                net_power += comp.P.val

    # Take absolute value due to TESPy sign conventions
    net_power = abs(net_power)

    # Calculate cycle exergy efficiency
    if net_power > 0:
        cycle_ex_eff = ex_p_total / net_power
    else:
        cycle_ex_eff = 0.0

    return round(cycle_ex_eff, 4)


def _calculate_total_exergy_destruction(df_components):
    """
    Calculate total exergy destruction across all components.

    cycle_Ex_D = Sum of all Ex_D values from all components

    Returns
    -------
    float
        Total exergy destruction in MW
    """

    if df_components.empty:
        print("Warning: No components found for total exergy destruction calculation")
        return 0.0

    cycle_Ex_D = df_components["Ex_D [MW]"].sum()

    return round(cycle_Ex_D, 4)
