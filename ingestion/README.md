# Ingestion (Member 1)

Build the contract-aligned Parquet staging layer from locally downloaded source files. Raw source files remain untouched. Each output table gets a JSON row-count/profile report next to its Parquet file. Rows with invalid required values are saved under `data/staging/rejected/` with their source file, row number, and reason. Older FAERS case versions are filtered on purpose, along with their child rows.

The shared NDC helper is `common.ndc.normalize_ndc11`. It keeps the code as text, adds leading zeros by FDA segment for dashed package codes, and pads plain 10-digit NADAC values on the left.

## Install

From the repository root:

```powershell
py -m pip install -r requirements-dev.txt
```

## Expected raw-file layout

```text
data/raw/
├── DEMO*.txt
├── DRUG*.txt
├── REAC*.txt
├── OUTC*.txt
├── rxnorm/
│   ├── RXNCONSO.RRF
│   ├── RXNSAT.RRF
│   └── RXNREL.RRF
├── ndc/
│   ├── product.txt
│   └── package.txt
├── nadac/
│   └── *.csv
└── egypt/
    └── *.csv
```

FAERS files are FDA delimiter-separated text files. RxNorm RRF files and NDC tab-separated files should be extracted before running. NADAC and Egypt inputs are CSV files. Downloading is intentionally separate from ingestion: source releases have different terms and RxNorm distribution may require UMLS credentials. Do not commit full source datasets or credentials.

## Run

Run one source or all sources from the repository root:

```powershell
py -m ingestion.run --source faers
py -m ingestion.run --source rxnorm
py -m ingestion.run --source ndc
py -m ingestion.run --source nadac
py -m ingestion.run --source egypt
py -m ingestion.run --source all
```

By default, outputs are written to `data/staging/`. Override paths when needed:

```powershell
py -m ingestion.run --source nadac --raw-dir data/raw --staging-dir data/staging
```

Try the complete flow on the small fictional sample before using real data:

```powershell
py -m ingestion.run --source all --raw-dir data/sample/raw --staging-dir data/sample/staging
```

For `--raw-dir`, FAERS inputs are read directly from that directory; each other source is read from its named subdirectory.

## Contract and validation

Output schemas are defined by `contracts/contracts.yaml`. Run the repository checks with:

```powershell
py -m pytest
py -m ruff check .
```

The sample input files are fictional and include a few bad rows so you can see the reject and profile outputs. The tests compare all 11 ingestion Arrow schemas against the YAML contract. Do not include downloaded production releases in Git.
