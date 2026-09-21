# main/

**Entry-point scripts** used to run complete workflows and specific plant cases by calling the modules and functions defined in `src`.

No core modelling, numerical, or algorithmic logic should be implemented in this folder. The `main` folder only orchestrates the execution of the workflows.

For the current case, **`standalone_base_recup_hthp.py`** creates the configured TESPy network, assembles the corresponding plant model from `src`, and runs the design-point simulation.

The validation workflow is executed through **`validation_hthp.py`**, which runs the validation functions defined in `src/validation` and compares the calculated plant results with the reference data stored in `data/validation`.

As the repository develops, the entry-point scripts will also handle the execution of **post-processing, visualization, and output generation** using the corresponding modules in `src`.

## Post-processing and plotting phase

For the current case the post-processing consists in the generation of relevant plots. The plant's T-s diagram is generated through `plot_ts_diagram`, the temperature profile in the Sink component is also generated through `plot_hx_diagram`. Following, performance and sizing parameters are displayed in generated tables respectively through `generate_performance_parameters_table` and `generate_sizing_parameters_table`. Secondly, the exergy analysis is generated through `get_exergy_analysis` and a breakdown of exergy destruction within components is shown through `plot_exergy_destruction` function.

The general workflow is:

**src → plant creation and modelling → simulation → validation/post-processing → results**
