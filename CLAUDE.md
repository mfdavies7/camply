# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

spotsnagger is a campsite-availability finder. This working copy has been cut down to **GoingToCamp only** (Canadian parks): the Recreation.gov, UseDirect/ReserveCalifornia and Yellowstone/Xanterra providers, their searches, tests, cassettes and docs have been removed. Don't reintroduce references to them; leftover mentions (e.g. `RecDotGov*` container names, pyproject keywords) are legacy.

## Commands

Tooling is `uv` + `task` (Taskfile.yaml). `UV_LOCKED=1` is set, so run `task lock` after changing dependencies.

- `task install` — sync deps (all extras) and install pre-commit hooks
- `task test` — `uv run -- pytest` (xdist `-n auto` + coverage are in pytest addopts); pass args after `--`
- Single test: `uv run -- pytest tests/search_providers/test_goingtocamp_search.py::test_name -n 0`
- `task lint` / `task fmt` / `task fix` — ruff check / ruff format
- `task check` — mypy on `spotsnagger/`
- `task run -- spotsnagger <subcommand>` — run the CLI; `task docs` — mkdocs serve

Tests need `PUSHOVER_PUSH_TOKEN`/`PUSHOVER_PUSH_USER` set (Taskfile sets placeholders); set them yourself when calling pytest directly. Pytest treats warnings as errors (`filterwarnings = error`).

## Testing conventions

- HTTP is recorded with pytest-vcr cassettes (`tests/**/cassettes/`). Mark tests with `vcr_cassette` from `tests/conftest.py`; `vcr_config` scrubs credentials. Use `--vcr-record=none` to ensure no new recordings.
- An autouse fixture freezes time to 2023-04-28 12:00 so cassette responses stay valid — search windows in tests must be relative to that date.
- CLI tests use the `cli_runner` fixture (`SpotSnaggerRunner.run_spotsnagger_command("spotsnagger ...")`) and `cli_status_checker`.

## Architecture

Three layers, wired by registries:

1. **Providers** (`spotsnagger/providers/`) — subclass `BaseProvider`; talk to the booking API (`make_http_request_retry`, rate limiting). `GoingToCamp` maps each recreation area to its own subdomain via `RECREATION_AREAS` in `going_to_camp/rec_areas.py` (adding a park = adding an entry there). `ProviderType` in `providers/__init__.py` is the union of providers.
2. **Searches** (`spotsnagger/search/`) — subclass `BaseCampingSearch`, set `provider_class`, and implement `get_all_campsites()`. The base class does everything else: date-window expansion, consecutive-night filtering (pandas DataFrames), continuous polling, offline-search file persistence, and notification dispatch. Register new searches in `__search_providers__` in `search/__init__.py`; `CAMPSITE_SEARCH_PROVIDER` is keyed by the provider class name and is what the CLI's `--provider` resolves against.
3. **Notifications** (`spotsnagger/notifications/`) — subclass `BaseNotifications`; registered by name in `CAMPSITE_NOTIFICATIONS` in `multi_provider_notifications.py`. `MultiNotifierProvider` fans out to several and sends a "last gasp" on fatal errors.

Entry points: `spotsnagger/cli.py` (rich-click; `DEFAULT_SPOTSNAGGER_PROVIDER = GoingToCamp`; provider precedence is subcommand flag > top-level `--provider` > default) and YAML search files (`utils/yaml_utils.yaml_file_to_arguments`, schema in `docs/yaml_search.json`). Data models are **pydantic v1** (`spotsnagger/containers/`, `AvailableCampsite`, `SearchWindow`, GoingToCamp API models in `gtc_api_responses.py`).

Configuration comes from env vars, with `~/.spotsnagger` loaded as a dotenv file (`config/notification_config.py`); `spotsnagger configure` writes it.

## Conventions

- Ruff with absolute imports only (relative imports banned outside tests), numpy-style docstrings. Python ≥3.9 support — avoid newer-only syntax.
- Commits use conventional commits; no emoji anywhere in the project (code, docs, commit messages); releases via semantic-release. Pre-commit blocks commits directly to `main`.
