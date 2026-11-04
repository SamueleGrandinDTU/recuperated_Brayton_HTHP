"""Entry-point script of the techno-economic assessment of the recuperated
Brayton high-temperature heat pump (HTHP) layouts.

Runs ``run_techno_economic_assessment`` for the four layouts:

    S-BR   : standalone, base recuperated
    S-IR   : standalone, intercooled recuperated
    TES-BR : TES-integrated, base recuperated
    TES-IR : TES-integrated, intercooled recuperated

For every layout it solves the design point, validates it where reference data
exist, and saves the diagrams and tables (performance, sizing, connections,
heat exchangers, exergy, component cost) in ``results/paper``.

Run it from the repository root, with the virtual environment active:

    python -m main.Brayton_hthp_techno_economic_assessment

This file will be extended as the operational optimisation, the LCOH analysis
and the comparison figures are added to ``run_techno_economic_assessment``.
"""

from src import run_techno_economic_assessment

run_techno_economic_assessment(
    layouts=["S-BR", "S-IR", "TES-BR", "TES-IR"],
    save_path="results/paper",
)
