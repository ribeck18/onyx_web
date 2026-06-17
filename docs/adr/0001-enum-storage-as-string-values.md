# Store enums as lowercase string values in non-native columns

All SQLAlchemy enum columns are mapped with `native_enum=False` (a `VARCHAR` + `CHECK` constraint rather than a Postgres native `ENUM`) and persist the enum's lowercase `.value` (e.g. `"submitted"`) via `values_callable`, not the member name.

We chose this because the app runs on SQLite in development and is headed for Postgres on a VPS: a non-native column produces an identical schema on both, and new enum members (especially additional `SubmitCode`s) can be added without `ALTER TYPE` migrations. The trade-off is giving up database-native enum typing in favor of a `CHECK` constraint, which we consider acceptable for the flexibility gained.
