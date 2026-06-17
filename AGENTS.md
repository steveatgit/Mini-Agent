# Repository Notes for Agents

## Local Python Environment

- When checking the user's terminal Python environment, use an interactive login zsh command so shell aliases and PATH customizations are loaded:

  ```bash
  zsh -lic 'python --version; python3 -m pytest --version'
  ```

- In the user's terminal, `python` is an alias for `python3`.
- The user's `python3` environment has `pytest` installed.
- This repository also has a project virtual environment at `.venv`; prefer `.venv/bin/python -m pytest` when the task should use repository-pinned dependencies.
