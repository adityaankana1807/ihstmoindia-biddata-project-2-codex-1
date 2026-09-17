# Dataset fields and provenance

All CSVs are UTF-8 with a BOM for Excel compatibility. Blank fields indicate unavailable values, not zero. Every generated CSV has a `data_kind` field. SHA-256 hashes, actual row counts and column lists are recorded in `data/processed/manifest.json`.

## Case import and synthetic cases

| Field | Format / meaning |
|---|---|
| case_id | Unique string; mandatory; at most 100 characters |
| incident_start | Mandatory timezone-aware ISO 8601, e.g. `2024-08-01T20:30:00+05:30` |
| incident_end | Optional interval end; defaults to start; must not precede start |
| city, state_ut | Mandatory source geography names; synthetic city labels are generator settings |
| latitude, longitude | Mandatory finite decimal degrees, -90..90 and -180..180 |
| crime_family | Mandatory research category, not a legally verified IPC/BNS mapping |
| target_type | Optional MO: house, shop, warehouse in the fixtures |
| entry_method | Optional MO: forced_lock, window, open_door |
| tool_weapon | Optional MO: crowbar, cutter, none; blank means unknown, `none` means observed absence |
| property_stolen | Optional fixture category: cash, jewellery, electronics |
| escape_mode | Optional fixture category: motorcycle, foot, car |
| narrative | Mandatory de-identified text; at most 10,000 characters |
| language | Fixture language code: en, hi, te, ta, kn, bn; not a certified language detector |
| data_kind | `synthetic` for generated cases; imported provenance remains the supplier's responsibility |
| generator_seed | Reproducibility identifier, excluded from the model |

Separate `synthetic_india_ground_truth.csv` contains case_id, series_id, offender_id, label_basis and data_kind. A shared generated offender defines a positive label. It is not a police or forensic finding. `synthetic_india_splits.csv` contains case_id, split, group_id and data_kind; all cases of one generated offender stay together.

## Official aggregate and derived data

`india_cybercrime_state_year.csv`: state_ut, year, crime_family, registered_cases, data_kind, source_url, source_release_date. The source's names are retained, including abbreviated union territories. Each row is a jurisdiction-year count, not an offence record.

`india_state_trends.csv`: counts for each of the three years; absolute and percentage change 2022–2023; national share in 2023; 2023 naive prediction equal to the 2022 value; absolute baseline error; data_kind and source_url. Source provenance remains linked to the official annexure. These numbers measure registration, not latent crime prevalence or individual criminal propensity.

`multilingual_mo_lexicon.csv`: concept, language, phrase, data_kind. Six concepts × six languages = 36 authored entries. Missing terms or translations receive no inferred concept. Expert linguistic validation has not been performed.

`synthetic_test_pairs.csv`: query_case, candidate_case, same_generated_offender (0/1), score, data_kind. Includes only non-overlapping historical test pairs. Keep ground-truth columns outside predictor inputs.

## Provenance and limits

The source snapshot was downloaded from the [official PIB release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241336&lang=1&reg=1) during this build. Its publication date is 17 March 2026; its observations cover 2021–2023. Source bytes and generated CSVs are hashed. Generation timestamps are UTC. Exact numerical extraction is reconciled against all three national totals.

The original workbook is a broader acquisition catalog, not evidence that every listed source has been acquired. This executable includes the sources and fixtures enumerated above only. It does not contain restricted CCTNS, ICJS, e-Prisons or e-Forensics records. Do not describe synthetic records as real FIRs or measured Indian offender behaviour.
