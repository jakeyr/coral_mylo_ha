# Guidelines for Automated Contributors

This repository hosts a Home Assistant integration written in Python. Follow these rules when contributing:

## Repository layout
- Integration code lives in `custom_components/coral_mylo/`.
- Tests live in `tests/` and should mirror the module structure.

## Coding style
- Python 3 with `async`/`await` for Home Assistant interactions.
- Use snake_case for modules and variables, PascalCase for classes.
- Include module and function/class docstrings.
- Initialize logging with `logging.getLogger(__name__)` and log via `_LOGGER`.
- Prefer f-strings for string formatting.

## Tooling
- This project uses [pre-commit](https://pre-commit.com) with `ruff` for linting and formatting.
- Before committing, run `pre-commit run --files <changed files>`.
- Tests are run with `pytest`. After changes, execute `pytest -q`.

## Contributions
- Store integration state in `hass.data[DOMAIN]` similar to existing code.
- Use `async_add_executor_job` for blocking calls.
- Provide tests for new functionality when feasible.
