# Report (draft)

## Approach

Single FastAPI service exposing both the product API (`/api/v1`) and the IncuBrix connector contract (`/connector/v1`). Connectors are Python classes registered by key; destinations are database rows with connection JSON.

## What works (v0.1 scaffold)

- Six connector implementations + YAML manifests  
- Rules engine (frequency, self-promo, links, AI disclosure, automation)  
- Async jobs with idempotent `POST /publish`  
- Certification flow (publish → status → delete) with evidence records  
- Docker Compose: API, Postgres, MinIO, unified platform mocks  

## Advanced (implemented in v0.2)

- CSV catalogue import (`POST /catalogue/import`)  
- AI rules capture via swappable mock adapter + human confirm  
- Per-destination tailoring (`POST /tailor`, default on publish)  
- `fetch_metrics` on Discourse, Dev.to, Ghost + `GET /metrics`  
- Recertification scheduler (30-day expiry demotion + alerts)  
- `openapi.yaml` via `scripts/export_openapi.py`  

## Outstanding (partial)

- Recommender with explainable scoring (audience, rules, certification, past publishes)  
- Labelled evaluation set: `catalogue/evaluation_labelled.json` + `POST /recommend/evaluate`  
- CLI: `scripts/run_recommender_eval.py` reports macro precision@10  

## Still optional

- 150+ real-world catalogue-only destinations for the submission spreadsheet  

## Cost

Default path: **$0** (mocks + local compose).
