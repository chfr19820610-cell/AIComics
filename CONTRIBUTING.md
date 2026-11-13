# Contributing to AIComics

Thanks for your interest in contributing! AIComics is an open-source AI donghua production system — every contribution matters.

## 🎯 Ways to Contribute

- 🐛 **Report bugs** — [Open an issue](https://github.com/chfr19820610-cell/AIComics/issues/new?template=bug_report.md)
- ✨ **Suggest features** — [Submit a feature request](https://github.com/chfr19820610-cell/AIComics/issues/new?template=feature_request.md)
- 📖 **Improve docs** — README, code comments, tutorials
- 🔧 **Submit code** — bug fixes, new features, optimizations
- 🌟 **Star & share** — helps others discover the project

## 🛠️ Development Setup

```bash
# Clone
git clone https://github.com/chfr19820610-cell/AIComics.git
cd AIComics

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-lock.txt

# Initialize demo database
PYTHONPATH="src" python -m aicomic.cli.main init-demo-db

# Run tests
PYTHONPATH="src" pytest tests/ -q
```

## 📋 Before You Submit a PR

1. **Run tests** — all must pass:
   ```bash
   PYTHONPATH="src" pytest tests/ -q
   ```

2. **Check imports** — make sure core modules load:
   ```bash
   PYTHONPATH="src" python -c "from aicomic.cli.main import main; print('OK')"
   ```

3. **Follow existing style** — match the code conventions already in the repo

4. **Update docs** — if your change adds a feature, update README.md

## 🔄 PR Process

1. Fork the repo and create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes, commit with clear messages
3. Open a PR using the template — fill in all sections
4. CI runs automatically — all 997+ tests must pass
5. Review feedback and iterate

## 📝 Commit Messages

Use clear, descriptive messages:

```
feat: add multi-language subtitle export
fix: ComfyUI workflow timeout on large batches
docs: update installation guide for Linux
test: add coverage for video_router fallback logic
```

## 🏗️ Architecture Overview

```
src/aicomic/
├── cli/          # Command-line interface
├── core/         # Business logic (manifest, pipeline, episodes)
├── providers/    # Provider abstraction (ComfyUI, Piper, Seedance)
├── characters/   # Character consistency system
├── video_synthesis/  # Video assembly pipeline
└── image_pipeline/  # Image generation + diagnostics
```

## 💬 Questions?

- [Open a discussion](https://github.com/chfr19820610-cell/AIComics/discussions)
- [Email](mailto:chfr19820610@gmail.com)

## 📄 License & Contributor Agreement

By contributing to AIComics, you agree that:

1. **Your contributions are licensed under Apache 2.0** — All contributions are licensed under the project's Apache License 2.0.

2. **You hold the copyright to your contributions** — You retain copyright in your contributions, but grant a perpetual, worldwide, non-exclusive, royalty-free license to use, modify, and distribute your contributions under the Apache 2.0 license.

3. **Your contributions are original or properly licensed** — You represent that your contributions are your own original work or that you have the necessary rights to contribute them, and that they do not infringe any third-party intellectual property rights.

4. **No patent retaliation** — Consistent with Apache 2.0, you grant a patent license for any patents you hold that are necessary to use your contributions.

For the full license terms, see [LICENSE](LICENSE).
