# Contributing to Gary

The project is in early design. The design doc is [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository layout

```
docs/                     design documents
data/                     local datasets (gitignored), see data/README.md
tests/fixtures/replays/   small committed replay set for tests and CI
```

Code folders are added as each component is built. The planned layout is in
[docs/ARCHITECTURE.md §11](docs/ARCHITECTURE.md#11-repository-layout-proposed).

## Data

Replays and other datasets are **not** stored in this repository.

1. Put downloaded replays in `data/raw/<source>/`, one folder per source (see
   [data/README.md](data/README.md)).
2. Record the source in [data/sources.yaml](data/sources.yaml).
3. Optionally set `GARY_DATA` to keep datasets on another drive.

Only replays that may be redistributed go in `tests/fixtures/replays/`. The rules are in
[tests/fixtures/replays/README.md](tests/fixtures/replays/README.md).

## Licensing

| What | License |
|---|---|
| Code we write | [MIT-0](LICENSE) |
| Docs, data files we create (taxonomies, schemas, labels, configs) | [CC0 1.0](LICENSE-CC0) |
| Third-party code copied into the repo | Its own license, kept in `third_party/<name>/` with its license file |
| Replay fixtures | Their source's license (e.g. STARDATA is BSD, attribution required) |

By contributing, you agree your contributions are released under these terms.

Rules:
- **Never copy GPL-licensed code into the repo.** Using GPL bots as opponents is fine.
- Copying permissive code (MIT, BSD, Apache-2.0) is fine if it goes in `third_party/` with its license and notices.
- **Never commit Blizzard game data** (`.mpq` files, sprites, sounds).
- **Don't copy text from guides or wikis.** Store our own structured claims and a link (Liquipedia is CC-BY-SA, which isn't compatible with CC0).
- Models fine-tuned from third-party weights keep the base model's license (e.g. Laya is Apache-2.0).

## Ground rules

- Gary plays in offline and custom games only. **Never on the Battle.net ladder.**
- Opponents in recorded or streamed games must have agreed to it.
- Gary never reads information a human player couldn't see.
