# Python utility edge case

`normalize_slug("Hello  World!")` currently keeps duplicate separators.

Expected:
- Duplicate separators are collapsed.
- Leading and trailing separators are removed.
- Existing lowercase input still works.
