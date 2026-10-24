# Sources and licences

| Component | Licence | Notes |
|-----------|---------|-------|
| FastAPI | MIT | API framework |
| SQLAlchemy | MIT | Persistence |
| MinIO client | Apache-2.0 | S3-compatible storage |
| PyJWT | MIT | Ghost Admin API JWT |
| Ghost (optional image) | MIT | `ghost:5-alpine` compose profile |
| Lemmy (optional image) | AGPL-3.0 | Only in `real-lemmy` profile; default path uses mocks |

Default certification path uses **local mocks** only (no posting to real communities).
