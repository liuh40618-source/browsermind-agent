# Contributing to BrowserMind

Thank you for your interest in contributing to BrowserMind! This document provides guidelines and instructions to help you get started.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Testing Requirements](#testing-requirements)
- [Submitting Issues](#submitting-issues)
- [Code of Conduct](#code-of-conduct)

## Development Environment Setup

### Prerequisites

- **Python 3.10+**
- **Git**
- **Node.js 18+** (for frontend development)

### Backend Setup

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/browsermind.git
   cd browsermind
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Install Playwright browsers:**

   ```bash
   playwright install chromium
   ```

5. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys and configuration
   ```

### Frontend Setup

1. **Install frontend dependencies:**

   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server:**

   ```bash
   npm run dev
   ```

## Code Style

### Python

- **Formatter:** [black](https://github.com/psf/black)
- **Linter:** [ruff](https://github.com/astral-sh/ruff)
- **Indentation:** 4 spaces
- **Encoding:** UTF-8
- **Line length:** 88 characters (black default)

Run linters before committing:

```bash
ruff check .
black --check .
```

Auto-fix formatting issues:

```bash
ruff check --fix .
black .
```

### General Guidelines

- Write clear, descriptive commit messages following [Conventional Commits](https://www.conventionalcommits.org/).
- Keep functions small and focused on a single responsibility.
- Add docstrings to all public functions, classes, and modules.
- Use type hints for function signatures.
- Avoid introducing new linting warnings.

## Submitting a Pull Request

Follow the **fork-and-branch** workflow:

1. **Fork** the repository on GitHub.

2. **Clone** your fork locally:

   ```bash
   git clone https://github.com/<your-username>/browsermind.git
   cd browsermind
   ```

3. **Create a feature branch** from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

   Use descriptive branch names such as `feature/add-search-provider`, `fix/memory-leak`, or `docs/update-readme`.

4. **Make your changes** and commit them:

   ```bash
   git add .
   git commit -m "feat: add support for custom search providers"
   ```

   Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `refactor:` for code refactoring
   - `test:` for adding or updating tests
   - `chore:` for maintenance tasks

5. **Push** your branch to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request** against the `main` branch of the upstream repository.

   In your PR description, include:
   - A clear summary of the changes
   - The motivation or problem being solved
   - Any relevant issue numbers (e.g., `Closes #42`)
   - Steps to test the changes (if applicable)

7. **Respond to review feedback** and push additional commits as needed.

### PR Checklist

Before submitting, ensure:

- [ ] Code follows the project's code style
- [ ] All tests pass (`pytest`)
- [ ] New tests are added for new functionality
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages follow Conventional Commits
- [ ] No unnecessary files are included

## Testing Requirements

All contributions must pass the existing test suite and include new tests for added functionality.

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=browsermind --cov-report=html
```

### Writing Tests

- Place tests in the `tests/` directory.
- Use descriptive test names that explain the expected behavior.
- Follow the Arrange-Act-Assert pattern.
- Mock external services (LLM APIs, browser instances) in unit tests.

## Submitting Issues

Before submitting an issue, please:

1. **Search existing issues** to avoid duplicates.
2. **Check the documentation** and README for relevant information.

### Bug Reports

When reporting a bug, include:

- A clear, descriptive title
- Steps to reproduce the behavior
- Expected behavior vs. actual behavior
- Environment details (OS, Python version, browser version)
- Relevant logs or error messages
- Screenshots (if applicable)

### Feature Requests

When requesting a feature, include:

- A clear description of the proposed feature
- The problem or use case it addresses
- Any alternative solutions you have considered
- Mockups or examples (if applicable)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## License

By contributing to BrowserMind, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

---

Thank you for contributing to BrowserMind!
