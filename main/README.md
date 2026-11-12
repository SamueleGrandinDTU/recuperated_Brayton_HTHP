# main/

**Entry-point scripts** used to run complete workflows by calling the modules and functions defined in `src`.

No core modelling, numerical, or algorithmic logic is implemented in this folder. The `main` folder only orchestrates the execution of the workflows.

The full techno-economic assessment of the paper is run through **`run_techno_economic_assessment`** (defined in `src/techno_economic_analysis.py` and called from the script in this folder). It takes as inputs:

- `layouts`: the plant layouts to simulate (S-BR, S-IR, TES-BR, TES-IR);
- `price_zones`: the electricity price zones where the plants operate (DK1, DE);
- `heat_demand_schedule`: the heat demand schedule typologies (fixed, variable);
- `comparison`: which figures to generate and which layouts, zones, demand schedules and scenarios each of them compares;
- `save_path`: where the results are saved (`results/paper`);
- `lcoh_results`: true/false input to provide the calculated yearly lcoh values skipping the execution of the whole lcoh analysis.

## Workflow

For each layout the plant is built and solved, validated (S-BR), and the performance, sizing and connection tables, the T-s and heat-exchanger diagrams, the exergy analysis, the TES tank sizing, the component cost, the operational optimization on 2025 prices and the LCOH are generated. Once all layouts are solved, the requested comparison plots are produced.

The general workflow is:

**src → plant creation and modelling → simulation → validation/post-processing → operation and LCOH → comparison → results**

The detailed steps and the `comparison` options are described in the repository design document (`docs/`).
