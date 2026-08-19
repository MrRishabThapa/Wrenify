# Contributing to Wrenify

Thanks for wanting to help improve Wrenify!

## Development Setup

```bash
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify
poetry install
poetry shell
```

## Running

```bash
# Launch the UI
poetry run wrenify

# CLI commands
poetry run wrenify --help
poetry run wrenify info
poetry run wrenify library
poetry run wrenify import path/to/song.mp3 --title "Title" --artist "Artist"
```

## Code Style

- Use type hints on all functions
- Follow PEP 8 (enforced by ruff)
- Docstrings on all public functions/classes
- Use loguru for logging (never print)
- Import CONFIG from wrenify.core.config

Run linter:
```bash
poetry run ruff check .
poetry run ruff format .
```

## Testing

```bash
poetry run pytest
```

## Commit Messages

Use conventional commits:
- `feat(scope): description` for new features
- `fix(scope): description` for bug fixes
- `docs(scope): description` for documentation
- `refactor(scope): description` for refactoring

## Pull Request Process

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes with tests
4. Run linter and tests
5. Submit PR with clear description
6. Link to any related issues
