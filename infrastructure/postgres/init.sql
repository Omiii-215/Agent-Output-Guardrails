-- Runs once when the local Postgres container initialises.
-- The owner (POSTGRES_USER) runs migrations; the application connects as
-- finguard_app, which receives the NOLOGIN app_runtime role from the
-- migrations and has no BYPASSRLS, DDL rights or table ownership.
CREATE ROLE finguard_app LOGIN PASSWORD 'finguard_app_dev' NOBYPASSRLS;
