# Sources and licences

| Component | Licence | Notes |
|-----------|---------|-------|
| FastAPI | MIT | API framework |
| SQLAlchemy | MIT | Persistence |
| MinIO client | Apache-2.0 | S3-compatible storage |
| PyJWT | MIT | Ghost Admin API JWT |
| Ghost | MIT | `ghost:5-alpine` in default `docker-compose.yml` |
| Lemmy | AGPL-3.0 | `dessalines/lemmy:0.19.6` + Postgres + pictrs in default compose |

Default certification path uses **local mocks** only (no posting to real communities).
