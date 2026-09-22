"""Create TESPy connections between previously instantiated plant
components, using a JSON specification file, and add them to a network.

The JSON file is a list of connection definitions::

    [
        {
            "label": "<connection label>",
            "source": "<source component label>",
            "source_id": <source outlet index>,
            "target": "<target component label>",
            "target_id": <target inlet index>
        },
        ...
    ]

``source`` and ``target`` must match keys of the ``components``
dictionary (e.g. as returned by ``set_plant_components``).
"""

import json
from typing import Dict, List

from tespy.connections import Connection
import tespy.components as tc
from tespy.networks import Network


def set_plant_connections(
    network: Network, components: Dict[str, tc.component], json_path: str
) -> None:
    """Load connection data, link the components, and add the resulting
    connections to a TESPy network.

    Parameters
    ----------
    network : tespy.networks.Network
        TESPy network the connections will be added to.
    components : dict[str, tespy.components.Component]
        Mapping of component label to instantiated TESPy component,
        as produced by ``set_plant_components``. Every ``source`` and
        ``target`` label referenced in the JSON file must be present
        here.
    json_path : str
        Path to a JSON file containing a list of connection
        definitions, as described in the module docstring.

    Returns
    -------
    None
        The connections are added to ``network`` in place via
        ``network.add_conns``.

    Raises
    ------
    KeyError
        If a ``source`` or ``target`` label in the JSON file is not
        found in ``components``.
    """
    with open(json_path, "r") as f:
        conn_data: List[dict] = json.load(f)

    connections = []
    for c in conn_data:
        # Retrieve the instantiated component objects from the dictionary
        source_obj = components[c["source"]]
        target_obj = components[c["target"]]

        # Create the TESPy Connection
        conn = Connection(
            source_obj, c["source_id"], target_obj, c["target_id"], label=c["label"]
        )
        connections.append(conn)

    # Unpack and add all connections to the TESPy network
    network.add_conns(*connections)
