# PageMaster

A personal document library — upload PDFs and web articles, extract them to clean
Markdown, and read, summarize, and discuss them. Built as a public, self-contained
showcase of clean **Domain-Driven Design + Hexagonal architecture**, developed
strictly test-first.

> **Status:** work in progress, built incrementally and test-first. Each capability
> lands as a red→green commit pair. This is an early stage — right now the app boots
> and serves a health check; features arrive batch by batch.

## Architecture

The backend follows a ports-and-adapters (hexagonal) layout under `src/pagemaster/`,
with dependencies pointing strictly inward (`entrypoints`/`adapters` → `services` →
`domain`):

- **`domain/`** — pure entities and ports; no framework or I/O.
- **`services/`** — application use cases, framework-agnostic.
- **`adapters/`** — concrete implementations of domain ports (database, storage, …).
- **`entrypoints/`** — driving adapters: the FastAPI app and routes.

Layers materialize as the capabilities that need them arrive.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Development

```bash
make sync     # install dependencies
make test     # run the test suite
make dev      # run the dev server at http://localhost:8000
```

Once running, check liveness:

```bash
curl http://localhost:8000/health   # {"status": "ok"}
```

## License

[MIT](LICENSE)
