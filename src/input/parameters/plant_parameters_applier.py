"""Apply connection and component parameters to a TESPy network from a
JSON specification file.

The JSON file has the structure::

    {
        "connections": {
            "<connection label>": {
                "fluid_engines": {"<fluid>": "<engine name>"},
                "fluid_wrapper_kwargs": {"<fluid>": {"<kwarg>": [...]}},
                ...additional keyword arguments passed to Connection.set_attr...
            }
        },
        "components": {
            "<component label>": {
                ...keyword arguments passed to Component.set_attr...
            }
        }
    }

Connection/component labels must already exist in the given TESPy
``Network`` (e.g. created via ``set_plant_components`` and connected
through ``set_plant_connections``).
"""

import json
from typing import Dict

import numpy as np
from tespy.networks import Network
from tespy.tools.fluid_properties import IncompressibleFluidWrapper

# Create a mapping dictionary for fluid engines
FLUID_ENGINES_MAPPING: Dict[str, type] = {
    "IncompressibleFluidWrapper": IncompressibleFluidWrapper
}


def set_plant_parameters(network: Network, json_path: str) -> None:
    """Load connection and component parameters from a JSON file and
    apply them to an existing TESPy network.

    Parameters
    ----------
    network : tespy.networks.Network
        TESPy network whose connections and components will be
        parameterized. Connections and components must already be
        present in ``network``.
    json_path : str
        Path to a JSON file with top-level ``"connections"`` and
        ``"components"`` sections, as described in the module
        docstring.

    Returns
    -------
    None
        The network is modified in place via ``set_attr``.

    Notes
    -----
    - For connections, ``fluid_engines`` string values are resolved
      against ``FLUID_ENGINES_MAPPING`` before being passed to
      ``set_attr``.
    - For connections, any list found inside ``fluid_wrapper_kwargs``
      is converted to a NumPy array, since TESPy's fluid property
      wrappers expect array-like data rather than plain Python lists.
    - Labels not found in the network are skipped with a warning
      printed to stdout, rather than raising an exception, so that a
      partially specified JSON file does not abort the whole run.
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    # 1. Apply parameters to connections
    for label, attrs in data.get("connections", {}).items():
        if label in network.conns.index:

            if "fluid_engines" in attrs:
                for fluid, engine_str in attrs["fluid_engines"].items():
                    if engine_str in FLUID_ENGINES_MAPPING:
                        attrs["fluid_engines"][fluid] = FLUID_ENGINES_MAPPING[
                            engine_str
                        ]

            # Convert JSON lists into NumPy arrays inside fluid_wrapper_kwargs
            if "fluid_wrapper_kwargs" in attrs:
                for fluid, kwargs in attrs["fluid_wrapper_kwargs"].items():
                    for key, val in kwargs.items():
                        if isinstance(val, list):
                            kwargs[key] = np.array(val)

            network.conns.loc[label, "object"].set_attr(**attrs)
        else:
            print(f"Warning: Connection label '{label}' not found in network.")

    # 2. Apply parameters to components
    for name, attrs in data.get("components", {}).items():
        if name in network.comps.index:
            network.comps.loc[name, "object"].set_attr(**attrs)
        else:
            print(f"Warning: Component '{name}' not found in network.")
