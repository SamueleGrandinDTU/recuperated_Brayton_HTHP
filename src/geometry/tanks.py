"""Thermal energy storage (TES) tank geometry.

This module sizes the TES tanks (dimensions, volume, mass) for the TES-
integrated plant configurations. The storage material is fixed to HITEC molten salt,
and tank shape is always a vertical cylinder, sized from its own mass and an
aspect ratio (or explicit D/H).

Each call to `calculate_tanks_geometry` returns one Tank object per
connection label passed in, exposed the same way TESPy exposes a
component's parameters (as attribute objects with a `.val`), so a Tank
can be used interchangeably with a TESPy component in downstream code:

    tank_hot, tank_cold = calculate_tanks_geometry(
        plant, "t1", "t2", storage_duration=8
    )
    tank_hot.V.val   # volume [m3]
    tank_hot.M.val   # mass [kg]
    tank_hot.H.val   # height [m]
    tank_hot.D.val   # diameter [m]
    tank_hot.E.val   # capacity [MWh]
"""

import math

# HITEC molten salt properties (fixed: this project always uses HITEC).
# cp: specific heat capacity [kJ/(kg*K)].
_HITEC_PROPERTIES = {"cp": 1.56}


def _tank_display_label(connection_label):
    """Turn a tank's connection label into a display label: the leading "t"
    is dropped and replaced with "tank " (e.g. "t1" -> "tank 1"). Falls back
    to the connection label unchanged if it doesn't start with "t".
    """
    text = str(connection_label)
    if text.lower().startswith("t"):
        return f"tank {text[1:]}"
    return text


class _Parameter:
    """Minimal container mimicking a TESPy component parameter (`dc_cp`-
    style), so a Tank's fields can be read as `tank.V.val`, matching how
    TESPy component attributes are accessed.
    """

    def __init__(self, val):
        self.val = val


class Tank:
    """A sized TES tank, exposed like a TESPy component.

    Attributes
    ----------
    label : str
        The connection label this tank was sized from.
    V, M, H, D, E : _Parameter
        Volume [m3], mass [kg], height [m], diameter [m] and energy
        capacity [MWh], each accessed via `.val` (e.g. `tank.V.val`).
    """

    def __init__(self, label, V, M, H, D, E):
        self.label = label
        self.V = _Parameter(V)
        self.M = _Parameter(M)
        self.H = _Parameter(H)
        self.D = _Parameter(D)
        self.E = _Parameter(E)

    def __repr__(self):
        return f"Tank('{self.label}')"


def calculate_tanks_geometry(
    plant,
    *connection_labels,
    storage_duration,
    D=None,
    H=None,
    aspect_ratio=0.3,
    safety_margin=1.1,
):
    """Size one TES tank per connection label given.

    Each connection label identifies the tank's own connection (mass flow,
    temperature and specific volume are all read from that single
    connection). Tank mass is the mass flow integrated over the storage
    duration; volume follows from the salt density at that connection's
    state; diameter and height either come from `D`/`H` directly or are
    derived from `volume` via `aspect_ratio` (H/D).

    Energy capacity (`E.val`) is shared logic across all tanks in one call:
    it is mass * cp_HITEC * dT / 3600 [MWh], where dT is the temperature
    difference between the hottest and coldest of the connections passed
    in (e.g. the hot vs. cold tank of a two-tank TES). This only produces a
    meaningful (non-zero) capacity when at least two connections with
    different temperatures are passed in the same call.

    Parameters
    ----------
    plant : tespy.networks.network.Network
        Solved plant network.
    *connection_labels : str
        One connection label per tank to size, e.g. "t1", "t2". Can also be
        given as a single list/tuple, e.g. ["t1", "t2"].
    storage_duration : float
        Storage (charging) duration [h].
    D : float, optional
        Fixed tank diameter [m], applied to every tank. If given together
        with H, overrides the aspect-ratio sizing.
    H : float, optional
        Fixed tank height [m], applied to every tank.
    aspect_ratio : float, default 0.3
        Height-to-diameter ratio (H/D) used when D/H are not given.
    safety_margin : float, default 1.1
        Multiplier applied to the calculated volume (1.1 = 10% margin).

    Returns
    -------
    list of Tank
        One Tank per connection label, in the same order as given.
    """
    # Accept either separate labels (plant, "t1", "t2", ...) or a single
    # list/tuple of labels (plant, ["t1", "t2"], ...).
    if len(connection_labels) == 1 and isinstance(connection_labels[0], (list, tuple)):
        connection_labels = tuple(connection_labels[0])

    if not connection_labels:
        raise ValueError("At least one connection label is required.")

    cp = _HITEC_PROPERTIES["cp"]

    masses = []
    volumes = []
    temperatures = []

    for label in connection_labels:
        conn = plant.conns.loc[label, "object"]

        mass_flow = conn.m.val  # [kg/s]
        T_tank = conn.T.val  # [°C]
        density = 1 / conn.vol.val  # [kg/m3]

        mass = mass_flow * (storage_duration * 3600)  # [kg]
        volume = (mass / density) * safety_margin  # [m3]

        masses.append(mass)
        volumes.append(volume)
        temperatures.append(T_tank)

    if len(connection_labels) > 1:
        delta_T = max(temperatures) - min(temperatures)
    else:
        print(
            "Warning: only one connection given, capacity (E) requires at "
            "least two tanks at different temperatures; setting E = 0."
        )
        delta_T = 0.0

    tanks = []

    print(f"\n{'=' * 100}")
    print("TES TANK GEOMETRY")
    print(f"{'=' * 100}")

    for label, mass, volume in zip(connection_labels, masses, volumes):
        if D is not None and H is not None:
            tank_D = float(D)
            tank_H = float(H)
        else:
            tank_D = ((4 * volume) / (math.pi * aspect_ratio)) ** (1 / 3)
            tank_H = aspect_ratio * tank_D

        capacity = (mass * cp * delta_T) / 3600 / 1000  # [MWh]

        tank = Tank(
            label=_tank_display_label(label),
            V=round(volume, 2),
            M=round(mass, 2),
            H=round(tank_H, 2),
            D=round(tank_D, 2),
            E=round(capacity, 3),
        )
        tanks.append(tank)

        print(
            f"Tank '{tank.label}': D = {tank.D.val} m, H = {tank.H.val} m, "
            f"V = {tank.V.val} m³, M = {tank.M.val} kg, "
            f"E = {tank.E.val} MWh"
        )

    print(f"{'=' * 100}")

    return tanks
