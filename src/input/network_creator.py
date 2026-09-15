"""
Network Creator Module
======================
Creates a network where to run the selected model with the default measurement units.
"""

from tespy.networks import Network


def create_configured_network():
    network = Network()
    network.units.set_defaults(
        temperature="degC",
        pressure="bar",
        enthalpy="kJ/kg",
        power="MW",
        heat="MW",
        entropy="kJ/kgK",
    )
    network.iterinfo = False
    return network
