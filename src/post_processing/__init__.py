"""Post-processing package"""

from .economic_plotting import plot_operational_strategy

from .cost_plotting import (
    plot_component_cost_stacked,
    plot_lcoh_scenarios_stacked,
    plot_delta_lcoh_analysis,
    plot_lcoh_breakdown_stacked,
)

from .exergy_plotting import (
    plot_exergy_destruction_stacked,
    plot_exergetic_efficiencies,
    plot_exergy_plots,
)

from .hx_diagram import plot_hx_diagram, save_hx_table

from .parameters_tables import (
    save_table_as_csv,
    save_table_as_png,
    generate_performance_parameters_table,
    generate_sizing_parameters_table,
    generate_connections_table,
)

from .plant_validation import validate_plant

from .ts_diagram import plot_ts_diagram

__all__ = [
    "plot_operational_strategy",
    "plot_component_cost_stacked",
    "plot_lcoh_scenarios_stacked",
    "plot_delta_lcoh_analysis",
    "plot_lcoh_breakdown_stacked",
    "plot_exergy_destruction_stacked",
    "plot_exergetic_efficiencies",
    "plot_exergy_plots",
    "plot_hx_diagram",
    "save_hx_table",
    "save_table_as_csv",
    "save_table_as_png",
    "generate_performance_parameters_table",
    "generate_sizing_parameters_table",
    "generate_connections_table",
    "validate_plant",
    "plot_ts_diagram",
]
