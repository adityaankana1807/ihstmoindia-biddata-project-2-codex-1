# I-HSTMO India

A runnable local research application with an explainable case-linkage algorithm, reproducible Indian aggregate data, new synthetic case datasets, evaluation, a browser interface, an HTTP API, and a Windows executable.

**The implemented model is a research baseline trained on synthetic data. It has not been validated on real Indian police cases.** The supplied manuscript is a proposal; its optional neural, network and legal-ontology components are not represented as completed experiments here.

## Start

Double-click `Start-IHSTMO.cmd` or `dist/I-HSTMO-India.exe`. The executable includes Python, the trained model, datasets and interface. It opens **http://127.0.0.1:8765**. Keep its console open while using it; press Ctrl+C to stop. Only one instance should use a given port.

Alternatively, with Python 3.11 or later:

```powershell
python run.py
# If port 8765 is already occupied:
python run.py --port 8787
```

There are no runtime pip dependencies, external API keys, CDNs or internet requirements. The server binds to localhost only. This is a local research application, not an authenticated multiuser production service.

## Use the application

1. **Regional trends:** inspect official registered cybercrime counts and year-to-year changes. Counts are not per-capita risk estimates.
2. **Case linkage:** filter generated cases by city, select a query and rank earlier cases. Expand a result to see spatial, temporal, MO, text and model contributions.
3. **Analyze CSV:** use `synthetic_india_cases.csv` as the format; choose a query or leave it blank for the latest occurrence. Up to 1,000 records are processed in memory. The model remains synthetic-trained even if other records are supplied. Only de-identified records appropriate for your authorised research should be used.
4. **Evaluation:** inspect offender-disjoint synthetic test performance and retrained ablations.
5. **Datasets & sources:** download CSVs, SHA-256 provenance manifest and evaluation JSON.

## Datasets

| File | Rows | Nature |
|---|---:|---|
| `india_cybercrime_state_year.csv` | 108 | Official NCRB counts reproduced from a PIB annexure, 36 states/UTs × 3 years |
| `india_state_trends.csv` | 36 | Derived changes, national shares and 2023 last-observation baseline errors |
| `synthetic_india_cases.csv` | 840 | New generated case fixtures in eight Indian city settings |
| `synthetic_india_ground_truth.csv` | 840 | Separate synthetic series/offender labels; never predictor inputs |
| `synthetic_india_splits.csv` | 840 | Deterministic train/validation/test assignments grouped by generated offender |
| `multilingual_mo_lexicon.csv` | 36 | Six concepts in English, Hindi, Telugu, Tamil, Kannada and Bengali; demo phrases |
| `synthetic_test_pairs.csv` | Generated during evaluation | Historical held-out pairs, labels and scores |

The synthetic dataset contains 120 series × 6 cases + 120 singletons = **840 records**, 240 generated offenders, seed **20260916**. City coordinates are approximate generator anchors, not measured offence locations. English and regional-language phrases are controlled fixtures, not representative language coverage. The synthetic property-crime data are **not disaggregated from** the real cybercrime totals.

Official source: [Ministry of Home Affairs / PIB, Cyber Awareness, 17 March 2026](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241336&lang=1&reg=1), NCRB annexure. The downloaded source HTML is saved in `data/raw/pib_2241336.html`. Totals are checked against the source: **2021: 52,974; 2022: 65,893; 2023: 86,420**. These are historical data, not a claim that 2023 remains the latest release. The provider retains ownership and applicable source terms; this project does not assert a new licence over third-party data.

## Reproduce, test and compile

```powershell
python scripts/reproduce.py
python -m compileall -q ihstmo scripts run.py
node --check web/app.js
python -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
```

Node is optional and only needed for the JavaScript syntax check. PyInstaller is isolated in `.build-venv`; it is a build-only dependency. [PyInstaller usage documentation](https://pyinstaller.org/en/stable/usage.html).

To explicitly refresh the original source snapshot, run `python scripts/build_datasets.py --refresh`, then `python scripts/reproduce.py`. Normal reproduction uses the saved snapshot and works offline. Generation intentionally replaces the named generated CSVs; do not place manual edits in generated files.

## Command-line ranking

```powershell
python -m ihstmo.cli --query SYN-IN-0000-05 --top 10 --out outputs/ranking.json
```

## API

| Route | Purpose |
|---|---|
| `GET /api/health` | Readiness and model mode |
| `GET /api/regional` | Official-derived state trends |
| `GET /api/cases?city=Delhi` | Synthetic cases; optional `q` filter |
| `GET /api/link?case_id=SYN-IN-0000-05&limit=10` | Historical candidate ranking |
| `POST /api/analyze` | JSON `{ "cases": [...], "query_id": "..." }` or `{ "csv": "...", "query_id": "..." }` |
| `GET /api/evaluation` | Synthetic evaluation and ablations |
| `GET /api/manifest` | Dataset provenance and hashes |
| `GET /download/<filename>` | Allowlisted dataset/report download |

See `docs/ALGORITHM.md` for equations and validation boundaries, and `docs/DATA_DICTIONARY.md` for import fields. Tests cover source reconciliation, label leakage, missing MO, time zones, invalid coordinates, metric ties, historical retrieval, source hashes and the HTTP workflow.

## Research boundaries

This release executes the two workflows end to end. It does not claim novel empirical superiority, a calibrated real-offender probability, district-level population risk, a neural multilingual encoder, an actual Hawkes point-process fit, a police co-offender network, a legally verified IPC–BNS crosswalk, or CCTNS/ICJS access. These require additional data and validation. A three-year aggregate panel supports descriptive comparisons and a minimal temporal baseline, not reliable long-horizon forecasting.

The original DOCX and XLSX outside this project were not edited.
