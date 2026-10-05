# Survival prediction under chemotherapy (NCT00119613)

Reproducible research prototype for predicting survival (OS and PFS) in an
oncology cohort from baseline clinical variables, with robust evaluation,
anti-leakage controls and transparent documentation.

**Disclaimer:** this repository is an academic prototype. It is not a clinical
device and must not be used for clinical purposes or patient-level decisions.

Bachelor's thesis (TFG) — BSc in Applied Data Science, Universitat Oberta de
Catalunya (UOC), 2025–2026. Author: Alfonso Esteban Lasso.

> Development history is preserved as-is: commit messages are in Spanish, as is
> most of the internal documentation under `docs/`.

## Repository structure

```
src/data/              ETL and synthetic data generation
src/preprocessing/     preprocessing fitted inside the validation loop (anti-leakage)
src/models/            Cox PH, RSF, XGBoost and model comparison
src/evaluation/        C-index, IBS, Brier, calibration, robustness, interpretability
src/reporting/         figures and tables for the thesis report
docs/                  decision_log.md, model_card.md, style_guide.md
data/                  metadata only (raw data lives in "SAS dataset/", never versioned)
outputs/                run artifacts (not versioned)
tests/                 pipeline smoke tests
environment.yml        conda environment with exact pinned versions
requirements.txt       pip equivalent with exact pinned versions
tools/                 KPI-1 reproducibility check: PowerShell script and reference SHA-256 hashes of the ETL outputs
package.json           Node tooling to build the thesis report, transparency package and slides (docs/scripts/)
```

## Input data

The cohort comes from the NESP-Oncology-20010145 study (NCT00119613), available
through Project Data Sphere. Raw clinical data is excluded by design for privacy
reasons and per the data-use agreement.

1. Request access on Project Data Sphere (NCT00119613).
2. Place the `.sas7bdat` files in a `SAS dataset/` folder at the project root.

Neither the raw data nor the derived subject-level dataset is ever versioned.

## Environment setup

With conda (recommended for strict reproducibility):

```bash
conda env create -f environment.yml
conda activate tfg-nesp
```

With pip:

```bash
pip install -r requirements.txt
```

Verify the installation:

```bash
python -c "import pandas, numpy, sksurv, sdv; print('OK')"
pytest tests/ -q
```

## End-to-end execution

Run every step from the project root with the environment activated.
Artifacts are written to `output/` (gitignored).

### Step 1: ETL and derived dataset construction

```bash
python src/data/etl_nesp_nct00119613.py
```

Produces `output/nesp_nct00119613_dataset.csv`, a data dictionary and a quality
manifest. Prerequisite: `.sas7bdat` files in `SAS dataset/`.

### Step 2: Modeling (Cox, RSF, XGBoost and comparison)

```bash
python src/models/compare_models.py
```

Runs the three models with k=5 CV and n=1000 bootstrap, and writes the
comparison table to `output/model_comparison.csv`.

To run a single model:

```bash
python src/models/cox_baseline.py
python src/models/rsf_model.py
python src/models/xgb_model.py
```

### Step 3: Full evaluation of the final model (Cox PH)

```bash
python src/evaluation/eval_cox_final.py
```

Produces calibration, Brier score and dynamic AUC with bootstrap bands for OS
and PFS.

### Step 4: Robustness and interpretability

```bash
python src/evaluation/robustness_cox.py
python src/evaluation/interpretability_cox.py
```

Produces subgroup analyses and SHAP values.

### Step 5: Synthetic data and re-identification risk

```bash
python src/data/synthetic_data.py
```

Generates a synthetic dataset with CTGAN, then evaluates TSTR utility,
membership inference with shadow models, k-anonymity and DCR. Estimated
runtime: 1–3 minutes on CPU.

Main artifacts: `output/synthetic_metrics.json` and four PNG figures.
The synthetic dataset itself (`output/synthetic_dataset.csv`) is not versioned.

**Note:** synthetic data is for methodological prototyping only; it does not
reinforce the conclusions of the main model.

## Recommended order for a full run

```
Step 1  ->  Step 2  ->  Step 3  ->  Step 4  ->  Step 5
```

Each step reads the previous step's artifacts from `output/`. The ETL step
cannot be skipped.

## Running the tests

```bash
pytest tests/ -v
```

The smoke tests cover:

- `test_preprocessor.py`: adaptive imputer and preprocessing pipeline.
- `test_pipeline_smoke.py`: anti-leakage, seeding, OOF predictions and C-index.
- `test_synthetic_smoke.py`: k-anonymity, DCR and pre-registered acceptance criteria.

All tests use internally generated synthetic data; the real dataset is not
required.

## Environment version control

Exact package versions are frozen in `environment.yml` and `requirements.txt`.
To generate an exact lock file:

```bash
pip freeze > requirements.lock.txt
```

## Anti-leakage: pipeline guarantees

- The preprocessor (imputation, scaling, encoding) is fitted exclusively on the
  training fold inside the k=5 CV loop.
- Predictors are baseline variables: AGE, SEXCD, B_ECOGN, B_WEIGHT, CADIAGM,
  B_HGB and MEDHX_N. Outcomes (DTH, DTHDY, PFSCD, PFSDY) and TXG are never
  included.
- Hyperparameter search (Optuna) operates on inner splits of the training fold;
  the test fold is never used for hyperparameter selection.
- Bootstrap evaluates OOF predictions (never the fold's training data).
- Absence of leakage is checked via performance stability across folds
  (CV% < 10%) and the smoke tests in `test_pipeline_smoke.py`.

## Reproducibility

Global seed: `SEED = 42` (defined in `src/models/cv_utils.py` and imported by
every script). To reproduce results exactly:

1. Use the same environment: `conda env create -f environment.yml`.
2. Place the same raw data in `SAS dataset/`.
3. Run the steps in order.
