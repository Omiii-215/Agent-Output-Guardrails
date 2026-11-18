# FinGuard API on Vercel (serverless mode)

Runs the FastAPI app as a Vercel Python function with Neon PostgreSQL. There is
no long-lived worker: queued jobs are processed at the end of each API request
(`FINGUARD_INLINE_JOBS=true`) and uploaded documents are stored in PostgreSQL
(`FINGUARD_OBJECT_STORE=database`). This deployment uses the development
sign-in on demo data only.

```bash
PYTHONPATH=. uv run python scripts/build_vercel_api.py
```

```bash
vercel deploy --prod --cwd deploy/vercel-api
```

Environment variables (Vercel project settings): `FINGUARD_ENV=development`,
`FINGUARD_DATABASE_URL` (runtime role, pooled URL, `postgresql+psycopg://`),
`FINGUARD_SERVERLESS_DB=true`, `FINGUARD_OBJECT_STORE=database`,
`FINGUARD_INLINE_JOBS=true`, `FINGUARD_WEB_ORIGIN` (the dashboard URL),
`FINGUARD_MAX_UPLOAD_BYTES=4000000` (Vercel request limit), and random values
for `FINGUARD_OBJECT_GRANT_SECRET`, `FINGUARD_FIELD_ENCRYPTION_KEY` and
`FINGUARD_SIMULATOR_WEBHOOK_SECRET`. Migrations run once from a workstation with
`scripts/db_bootstrap.py` using the owner URL.
