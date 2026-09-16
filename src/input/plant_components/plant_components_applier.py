"""Instantiate TESPy plant components from a JSON specification file.

The JSON file maps a component label (used as the TESPy component's
``label``) to a component-type name (a key in ``COMPONENT_MAPPING``),
e.g.::

    {
        "turbine": "Turbine",
        "compressor": "Compressor"
    }
"""

import json
from typing import Dict

import tespy.components as tc

# Dictionary mapping JSON strings to actual TESPy classes
COMPONENT_MAPPING: Dict[str, type] = {
    "Turbine": tc.Turbine,
    "Compressor": tc.Compressor,
    "HeatExchanger": tc.HeatExchanger,
    "SimpleHeatExchanger": tc.SimpleHeatExchanger,
    "Source": tc.Source,
    "Sink": tc.Sink,
    "CycleCloser": tc.CycleCloser,
}


def set_plant_components(json_path: str) -> Dict[str, tc.component]:
    """Load component definitions from a JSON file and instantiate them.

    Parameters
    ----------
    json_path : str
        Path to a JSON file mapping component labels (str) to
        component-type names (str). Component-type names must be keys
        of ``COMPONENT_MAPPING``.

    Returns
    -------
    dict[str, tespy.components.Component]
        Mapping of component label to the corresponding instantiated
        TESPy component, ready to be used when defining connections.

    Raises
    ------
    ValueError
        If a component-type name in the JSON file is not found in
        ``COMPONENT_MAPPING``.
    """
    with open(json_path, "r") as f:
        comp_data = json.load(f)

    components = {}
    for name, comp_type in comp_data.items():
        if comp_type in COMPONENT_MAPPING:
            # Instantiate the class using the name as the label
            components[name] = COMPONENT_MAPPING[comp_type](name)
        else:
            raise ValueError(f"Unknown component type: {comp_type}")

    return components
