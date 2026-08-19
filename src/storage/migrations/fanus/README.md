# Fanus database migrations

Create every schema change after the initial bootstrap as a numbered
`peewee-migrate` migration in this directory. Never change persisted models
without a matching migration and a restore-path test.
