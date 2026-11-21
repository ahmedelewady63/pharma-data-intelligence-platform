# FAERS raw files

Place all extracted quarterly FDA FAERS ASCII text files here, including the
`DEMO`, `DRUG`, `REAC`, and `OUTC` files for each available quarter. Keep the
downloaded raw files out of Git; only this instruction file is tracked.

The ingestion command reads all matching files from this folder, including
files inside optional year subfolders:

```powershell
py -m ingestion.run --source faers
```
