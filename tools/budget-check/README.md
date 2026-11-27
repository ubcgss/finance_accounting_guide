# Budget Integrity Check: developer notes

The guide page is `docs/tools/budget-check.md`. This
folder holds the tests; it is excluded from the published site (`_config.yml`).

## Files

| Path | What it is |
|------|------------|
| `assets/budget-check/index.html` | The browser page. Loads Pyodide 0.26.4 and openpyxl, then runs the checker on the dropped file. The file never leaves the browser. |
| `assets/budget-check/budget_checks.py` | All the checks. Pure Python (stdlib + openpyxl), so the same file runs in the browser, from the command line, and in the tests. |
| `tools/budget-check/tests/test_budget_checks.py` | unittest suite built on small synthetic workbooks. Never commit a real budget file here: this repository is public. |

## Commands (from the repository root)

Any Python 3.12+ with `openpyxl` installed works.

```bash
# Run the tests
python -m unittest discover -s tools/budget-check/tests

# Run the checker on a saved copy of the master
python assets/budget-check/budget_checks.py "<path to master.xlsx>" -o report.md

# Try the page locally (fetch() needs http://, not file://)
python3 -m http.server 8765
# then open http://localhost:8765/assets/budget-check/
```

## Changing a check

Each check is one function in `budget_checks.py`, with its settings
(`ALLOWED_CONSTANTS`, `REQUIRED_LINES`, `DRIVER_TABS`, tolerances) at the top of
the file. Add or update a test for every change, and run the checker on the
current master to confirm the number of findings still makes sense.

The command line and the page must produce the same report. The page passes the
file name and timestamp in, so the only difference is the "Generated" line.
