"""
src/__init__.py
===============
Central imports for the src package.
"""

from .input import (
    PLOT_STYLE,
    set_plant_parameters,
    set_plant_components,
    set_plant_connections,
)
from .models import (
    standalone_base_recup_hthp,
    standalone_base_recup_hthp_Benvenuti,
)

from .post_processing import (
    plot_operational_strategy,
    plot_exergy_destruction_stacked,
    plot_hx_diagram,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    validate_plant,
    plot_ts_diagram,
)

from .cost_analysis import calculate_component_cost

from .exergy_analysis import get_exergy_analysis

from .network_creator import create_configured_network

from .plant_operation import (
    Plant,
    optimize_operational_strategy,
)

__all__ = [
    "PLOT_STYLE",
    "set_plant_parameters",
    "set_plant_components",
    "set_plant_connections",
    "create_configured_network",
    "standalone_base_recup_hthp",
    "standalone_base_recup_hthp_Benvenuti",
    "plot_operational_strategy",
    "plot_exergy_destruction_stacked",
    "plot_hx_diagram",
    "generate_performance_parameters_table",
    "generate_sizing_parameters_table",
    "validate_plant",
    "plot_ts_diagram",
    "calculate_component_cost",
    "get_exergy_analysis",
    "create_configured_network",
    "Plant",
    "optimize_operational_strategy",
]
