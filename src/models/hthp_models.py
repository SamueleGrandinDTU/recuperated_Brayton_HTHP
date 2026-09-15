"""Assemble a specific TESPy plant configuration (components, connections,
and parameters) into a TESPy network.

Each concrete model class below corresponds to one plant case and simply
points ``BaseHTHPModel`` at the three JSON files (under ``src/input/``)
that describe it: which components exist, how they are connected, and
which parameter values to apply. Building the model into a network is
then a matter of instantiating the class and calling ``build_into``.
"""

from pathlib import Path

from tespy.networks import Network

from src import set_plant_components, set_plant_connections, set_plant_parameters

# Absolute path to src/input/, resolved relative to this file so the
# module works regardless of the caller's current working directory.
BASE_INPUT_DIR = Path(__file__).resolve().parent.parent / "input"


class hthp_model:
    """Base class to automatically construct and parameterize a TESPy
    high-temperature heat pump (HTHP) plant from JSON specification files.

    Parameters
    ----------
    comp_file : str
        Filename of the component specification, located under
        ``src/input/plant_components/``.
    conn_file : str
        Filename of the connection specification, located under
        ``src/input/plant_connections/``.
    data_file : str
        Filename of the parameter specification, located under
        ``src/input/plant_data/``.
    """

    def __init__(self, comp_file: str, conn_file: str, data_file: str):
        self.comp_json = BASE_INPUT_DIR / "plant_components" / comp_file
        self.conn_json = BASE_INPUT_DIR / "plant_connections" / conn_file
        self.data_json = BASE_INPUT_DIR / "plant_data" / data_file

    def build_into(self, network: Network) -> None:
        """Construct this specific plant configuration into the provided
        TESPy network.

        Parameters
        ----------
        network : tespy.networks.Network
            TESPy network to populate with this model's components,
            connections, and parameters.

        Returns
        -------
        None
            The network is modified in place.
        """
        print(f"Building {self.__class__.__name__} topology...")

        # 1. Components
        components = set_plant_components(self.comp_json)
        # 2. Connections
        set_plant_connections(network, components, self.conn_json)
        # 3. Parameters
        set_plant_parameters(network, self.data_json)

        print(f"Successfully configured {self.__class__.__name__}.")


# --- Specific Plant Configurations ---


class standalone_base_recup_hthp(hthp_model):
    """Standalone, base, recuperated HTHP configuration."""

    def __init__(self):
        super().__init__(
            comp_file="standalone_base_recup_hthp_components.json",
            conn_file="standalone_base_recup_hthp_connections.json",
            data_file="standalone_base_recup_hthp_data.json",
        )
