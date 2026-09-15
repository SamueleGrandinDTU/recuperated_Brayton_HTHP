# main/

**Entry-point scripts** used to run complete workflows and specific plant cases by calling the modules and functions defined in `src/`.

No core modelling, numerical, or algorithmic logic should be implemented in this folder. The `main/` folder only orchestrates the execution of the workflows.

For the current case, **`standalone_base_recup_hthp.py`** creates the configured TESPy network, assembles the corresponding plant model from `src/`, and runs the design-point simulation.

As the repository develops, the entry-point scripts will also handle the execution of **post-processing, visualization, and output generation** using the corresponding modules in `src/`.

The general workflow is:

**`src/` → plant creation and modelling → simulation → post-processing → results**