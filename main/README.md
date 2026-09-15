# main/

**Entry-point scripts** to run complete workflows (e.g. simulations, parameter sweeps, or case studies) by calling components (i.e. scripts) from `src/`. No core logic should be implemented here.

No implementation of algorithmic logic (e.g. solver, discretization, boundary conditions, etc) is allowed in this folder. 

**`main/` must only orchestrate calls to `src/`** to run complete workflows, including input reading from `data` and post processing: visualizatio and writing outputs in `results`
