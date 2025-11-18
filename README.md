# Weather Model Selection System

Asset-centric weather forecast verification and intelligent model selection system.

## Quick Start
```bash
cd ~/projects/weather-model-selector
source venv/bin/activate
```

## Configuration

Edit `.env` and add your Anthropic API key:
```bash
nano .env
```

Get your API key from: https://console.anthropic.com/

## Usage

Start Claude Code for development assistance:
```bash
claude-code
```

## Verify Installation
```bash
python scripts/verify_setup.py
```

## Project Structure

- `src/` - Source code
  - `collectors/` - Data collection scripts
  - `processors/` - Data processing
  - `verification/` - Forecast verification
  - `api/` - REST API
  - `ml/` - Machine learning models
- `data/` - Data storage (not in git)
- `tests/` - Test suite
- `scripts/` - Utility scripts
- `notebooks/` - Jupyter notebooks

## Development Roadmap

See the roadmap artifact for detailed development phases.
