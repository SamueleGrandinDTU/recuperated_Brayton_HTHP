# data/

Stores input datasets required to run simulations or analyses. Raw data should be immutable and clearly separated from processed data when applicable.

- `raw/` - Original, unprocessed data files
- `processed/` - Cleaned and preprocessed datasets ready for analysis

Files in this directory should be documented with their sources and processing steps.

### Validation

The validation data contains the **reference data for the Benvenuti recuperated configuration**, stored in CSV format and used to validate the corresponding plant model. The dataset contains the reference thermodynamic state points required for comparison with the calculated plant results.