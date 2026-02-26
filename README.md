# player-rankings

> ⚠️ This project is currently under active development. Structure, interfaces, and functionality are subject to change.

## Overview

A modular pipeline for deriving player rankings in padel, built around three core stages:

1. **Scraping** — data collection via a private submodule (restricted access)
2. **Pipeline** — consolidation, normalisation, and feature engineering from raw scraped data
3. **Models** — standalone ranking models producing player ratings, leaderboards, and win probabilities

The ranking models are designed to be fully decoupled from data collection, making them portable for use in external applications.

---

## Repository Structure

```
player-rankings/
├── src/
│   ├── constants.py        # shared named keys and enums
│   ├── pipeline/           # consolidation, feature engineering, data loaders
│   ├── models/             # ranking models (ratings, leaderboard, win probability)
│   └── domain/             # core entities (Player, Match, Tournament)
├── config/
│   ├── default.yaml        # default configuration and model parameters
│   └── local.yaml          # local overrides (gitignored, not committed)
├── data/                   # gitignored, never committed
├── scraper/                # private submodule (restricted access)
├── tests/                  # test suite with fixture data
├── notebooks/              # exploratory analysis
├── Makefile                # pipeline step runner
└── pyproject.toml
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip

### Installation

```cmd
git clone https://github.com/DaanHoepman/player-rankings.git
cd player-rankings
pip install -e .
pip install -r requirements.txt
```

### Local Configuration

Copy the default config and add any local overrides:

```cmd
cp config/default.yaml config/local.yaml
```

`config/local.yaml` is gitignored and should never be committed.

---

## Running the Pipeline

```cmd
# Full pipeline (consolidation + feature engineering)
make pipeline

# Individual steps
make consolidate
make features

# Run tests
make test
```

> **Note:** The `make scrape` command requires access to the private scraper submodule and is restricted to authorised users only.

---

## Testing

The test suite runs entirely against fixture data and requires no real scraped data:

```cmd
pytest tests/
```

---

## Status

| Component | Status |
|---|---|
| Project structure | ✅ In progress |
| Scraper | 🔒 Private |
| Pipeline | 🚧 In progress |
| Domain entities | 🚧 In progress |
| Ranking models | 🚧 In progress |
| Tests | 🚧 In progress |

---

## Contributing

This repository is currently in early development. Please reach out before making any contributions.
