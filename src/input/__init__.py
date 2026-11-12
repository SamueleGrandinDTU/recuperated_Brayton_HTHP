"""Input package"""

from .styling import create_figure, save_figure, add_legend, PLOT_STYLE
from .parameters import set_plant_parameters
from .components import set_plant_components
from .connections import set_plant_connections

__all__ = [
    "create_figure",
    "save_figure",
    "add_legend",
    "PLOT_STYLE",
    "set_plant_parameters",
    "set_plant_components",
    "set_plant_connections",
]
