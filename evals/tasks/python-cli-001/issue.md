# Python CLI argument parsing bug

The demo CLI accepts `--name`, but passing an empty string prints an unclear greeting.

Expected:
- Empty names should produce a validation error.
- Existing valid names should keep working.
