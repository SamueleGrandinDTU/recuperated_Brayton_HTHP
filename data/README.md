# data/

Stores input datasets required to run simulations or analyses. Raw data should be immutable and clearly separated from processed data.

- `raw/` - Original, unprocessed data files
- `processed/` - Cleaned and preprocessed datasets read by the code

Files in this directory should be documented with their sources and processing steps.

### Validation

`processed/Benvenuti_validation_recuperated.csv` contains the reference state points of the recuperated Brayton heat pump of **Benvenuti et al. (2024)**, used to validate the corresponding plant model (S-BR layout) against the calculated plant results.

### Electricity prices

- `raw/electricity_prices/` contains the original hourly day-ahead prices of 2025 for several bidding zones (`Day-ahead_prices_202501010000_202601010000_Hour.csv`) [Source: https://www.smard.de/].
- `processed/electricity_prices/` contains the files read by the code:
  - `dk1_electricity_prices_2025.csv` and `de_electricity_prices_2025.csv`: hourly DK1 and DE prices of 2025, used by the operational optimization.
  - `dk1_energinet_2025_2050_scenarios.csv` and `de_vbw_2025_2050_scenarios.csv`: yearly price scenarios (low, central, high) from 2025 to 2050 (Energinet and VBW), given as factors relative to 2025. Intermediate years are linearly interpolated. Only the Energinet predictions are used by the LCOH analysis.