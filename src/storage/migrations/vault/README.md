# Counselor vault migrations

Create every schema change after the initial bootstrap as a numbered
`peewee-migrate` migration in this directory. Vault migrations must preserve
the cross-database `student_id` UUID relationship without copying note content
to `fanus.db`.
