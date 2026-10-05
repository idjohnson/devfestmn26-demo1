# Setup & Docker User Guide

**Review App** is an automated code review application that audits a repository's codebase and Git commit history against a markdown checklist. It supports either **Vertex AI (Gemini)** or **Ollama** as an LLM backend and can be run directly via Docker or as a local Python script.

---

## Table of Contents

1. [Quick Cheatsheet (Docker)](#quick-cheatsheet-docker)
2. [Docker Usage Guide](#docker-usage-guide)
   - [How Docker Execution Works](#how-docker-execution-works)
   - [Option 1: Using the Pre-built GHCR Image](#option-1-using-the-pre-built-ghcr-image)
   - [Option 2: Building the Image Locally](#option-2-building-the-image-locally)
   - [Running with Vertex AI / Gemini](#running-with-vertex-ai--gemini)
   - [Running with Ollama (Host Networking)](#running-with-ollama-host-networking)
   - [Volume Mounting Guide](#volume-mounting-guide)
     - [Mounting Current Directory](#1-mounting-current-directory)
     - [Reviewing an External Repository](#2-reviewing-an-external-repository)
     - [Mounting a Custom Checklist](#3-mounting-a-custom-checklist)
     - [Writing Output Reports to Host](#4-writing-output-reports-to-host)
   - [Using an Environment File (`.env`)](#using-an-environment-file-env)
   - [Docker Compose Alternative](#docker-compose-alternative)
3. [Local Python Usage](#local-python-usage)
   - [Virtual Environment Setup](#virtual-environment-setup)
   - [Running Directly with Python](#running-directly-with-python)
4. [Backend Configuration & Required Variables](#backend-configuration--required-variables)
5. [GitHub Actions & Container Registry (GHCR)](#github-actions--container-registry-ghcr)
6. [Checklist Rules Format & Examples](#checklist-rules-format--examples)
7. [Exit Codes Reference](#exit-codes-reference)
8. [Running Tests](#running-tests)

---

## Quick Cheatsheet (Docker)

### Run with Gemini
```bash
docker run --rm \
  -v "$(pwd)":/repo \
  -e GEMINI_KEY="your-gemini-api-key" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  ghcr.io/<owner>/reviewapp:latest
```

### Run with Ollama
```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)":/repo \
  -e OLLAMA_URL="http://host.docker.internal:11434" \
  -e OLLAMA_MODEL="llama3" \
  ghcr.io/<owner>/reviewapp:latest
```

---

## Docker Usage Guide

### How Docker Execution Works

When Review App runs in Docker:
1. The container image has Python 3.12, Git, and all dependencies installed.
2. The target repository on the host is mounted into the container at `/repo`.
3. The app inspects `/repo` (Git history, branches, file tree, source code) and checks it against a `.checklist` file.
4. LLM credentials and configurations are passed into the container via `-e` environment variables.

---

### Option 1: Using the Pre-built GHCR Image

When pushed by GitHub Actions, the image is available via GitHub Container Registry:

```bash
docker pull ghcr.io/<owner>/reviewapp:latest
```

Replace `<owner>` with your GitHub username or organization name.

---

### Option 2: Building the Image Locally

If you are developing or prefer to build locally from source:

```bash
docker build -t review-app .
```

---

### Running with Vertex AI / Gemini

Pass your Gemini API key and model name via `-e`:

```bash
docker run --rm \
  -v "$(pwd)":/repo \
  -e GEMINI_KEY="your-gemini-api-key" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  review-app
```

*(Optional Vertex AI variables: `-e VERTEXAI=true -e GOOGLE_CLOUD_PROJECT=<project_id> -e GOOGLE_CLOUD_LOCATION=<region>`)*.

---

### Running with Ollama (Host Networking)

When Ollama runs locally on your machine outside Docker, the container needs to route traffic to the host.

1. Ensure Ollama is running and listening:
   ```bash
   ollama serve
   ollama pull llama3
   ```
2. Run the container with `--add-host` to resolve `host.docker.internal`:
   ```bash
   docker run --rm \
     --add-host=host.docker.internal:host-gateway \
     -v "$(pwd)":/repo \
     -e OLLAMA_URL="http://host.docker.internal:11434" \
     -e OLLAMA_MODEL="llama3" \
     review-app
   ```

> **Tip for Linux users:** `--add-host=host.docker.internal:host-gateway` maps `host.docker.internal` to the host gateway IP. On macOS and Windows Docker Desktop, this is enabled by default.

---

### Volume Mounting Guide

#### 1. Mounting Current Directory
To evaluate the project you are currently in:
```bash
docker run --rm \
  -v "$(pwd)":/repo \
  -e GEMINI_KEY="$GEMINI_KEY" \
  -e GEMINI_MODEL="$GEMINI_MODEL" \
  review-app
```

#### 2. Reviewing an External Repository
To evaluate a different repository on your filesystem without changing directories:
```bash
docker run --rm \
  -v "/path/to/another-project":/repo \
  -e GEMINI_KEY="$GEMINI_KEY" \
  -e GEMINI_MODEL="$GEMINI_MODEL" \
  review-app
```

#### 3. Mounting a Custom Checklist
By default, the container looks for `/repo/.checklist`. You can mount any external checklist file into the container and point `REPO_CHECKLIST` to it:

```bash
docker run --rm \
  -v "$(pwd)":/repo \
  -v "/path/to/company-security-checklist.md":/checklists/security.md:ro \
  -e REPO_CHECKLIST="/checklists/security.md" \
  -e GEMINI_KEY="$GEMINI_KEY" \
  -e GEMINI_MODEL="$GEMINI_MODEL" \
  review-app
```

#### 4. Writing Output Reports to Host
Because `/repo` is mounted to your host folder, writing an output report to `/repo/report.md` will save it directly into your current directory on the host:

```bash
docker run --rm \
  -v "$(pwd)":/repo \
  -e GEMINI_KEY="$GEMINI_KEY" \
  -e GEMINI_MODEL="$GEMINI_MODEL" \
  review-app \
  --output /repo/review-report.md \
  --format markdown
```

---

### Using an Environment File (`.env`)

Instead of passing environment variables individually on the command line, store them in a `.env` file:

```bash
# .env file
GEMINI_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
# OR:
# OLLAMA_URL=http://host.docker.internal:11434
# OLLAMA_MODEL=llama3
```

Run with `--env-file`:
```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)":/repo \
  review-app
```

---

### Docker Compose Alternative

For routine local runs, you can define a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  review:
    image: review-app
    build: .
    volumes:
      - .:/repo
    environment:
      - GEMINI_KEY=${GEMINI_KEY}
      - GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}
      # - OLLAMA_URL=http://host.docker.internal:11434
      # - OLLAMA_MODEL=llama3
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Run with:
```bash
docker compose run --rm review
```

---

## Local Python Usage

### Virtual Environment Setup

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install requirements:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Running Directly with Python

```bash
# With Gemini
export GEMINI_KEY="your-gemini-key"
export GEMINI_MODEL="gemini-2.5-flash"
python review.py

# With Ollama
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3"
python review.py

# With custom options
python review.py --checklist custom_checklist.md --format json --output report.json
```

---

## Backend Configuration & Required Variables

The application strictly validates configuration and requires **one** of the two backend pairs:

| Variable | Description | Backend | Required |
| :--- | :--- | :--- | :--- |
| `GEMINI_KEY` | Gemini API Key (or `GEMINI_API_KEY`) | Vertex AI / Gemini | Yes (for Gemini) |
| `GEMINI_MODEL` | Gemini Model (e.g. `gemini-2.5-flash`) | Vertex AI / Gemini | Yes (for Gemini) |
| `OLLAMA_URL` | Ollama URL (e.g. `http://localhost:11434`) | Ollama | Yes (for Ollama) |
| `OLLAMA_MODEL` | Pulled Ollama Model (e.g. `llama3`) | Ollama | Yes (for Ollama) |
| `REPO_CHECKLIST` | Path to checklist markdown file | Any | No (default: `.checklist`) |
| `REPO_PATH` | Path to repository | Any | No (default: `.`) |

---

## GitHub Actions & Container Registry (GHCR)

The repository includes a pre-configured GitHub Actions workflow at:
[`.github/workflows/docker-publish.yml`](file:///home/isaac/Workspaces/reviewApp/.github/workflows/docker-publish.yml)

### Workflow Capabilities:
- **Builds and pushes multi-tag Docker images** to GitHub Container Registry (`ghcr.io`).
- **Triggers:**
  - Pushes to the `main` branch (tags image as `latest` and `main`).
  - Git release tags (e.g., `v1.0.0`).
  - Pull requests (builds image to verify syntax and dependencies without publishing).
  - Manual triggers via GitHub UI (`workflow_dispatch`).
- **Authentication:** Uses the automatic `${{ secrets.GITHUB_TOKEN }}` with `packages: write` permission.

### Pulling the Published Image
Once the workflow runs in your GitHub repository, the container is published at:
```bash
docker pull ghcr.io/<your-github-username>/reviewapp:latest
```

---

## Checklist Rules Format & Examples

Checklist files are markdown documents containing rules to test against the repository. The LLM evaluator receives:
1. **Full Git Commit History:** author, committer, date, commit hash, commit message subject and body.
2. **Git Working Tree Status & Branch.**
3. **Repository File Tree:** full directory structure (filtering cache and build artifacts).
4. **Source Code & Documentation:** file contents up to configurable size limits.

### Sample `.checklist`
```markdown
1. ensure every commit mentions a Vikunja ticket. These start with "#nnn" where n is positive number
2. ensure every commit has a committer
3. check that the README.md is up to date with project description and setup
4. ensure there are no hardcoded secrets or passwords in the source files
5. ensure requirements.txt exists and specifies package versions
```

---

## Exit Codes Reference

| Exit Code | Meaning | CI/CD Behavior |
| :---: | :--- | :--- |
| **`0`** | **PASSED:** All checklist rules were satisfied (or returned warnings). | CI pipeline succeeds. |
| **`1`** | **FAILED:** One or more checklist rules were violated. | CI pipeline fails step. |
| **`2`** | **CONFIG/ERROR:** Missing credentials, missing checklist, or LLM failure. | CI pipeline reports error. |

To allow CI pipelines to continue even when rules fail, pass `--no-fail-exit`.

---

## Running Tests

Automated unit tests are implemented using `pytest`:

```bash
pytest -v
```

This runs tests verifying:
- Configuration parsing and error handling for missing/partial backends
- Context collection (Git history, file reading, ignore patterns)
- Mocked Gemini and Ollama backend requests
- JSON parsing and markdown report rendering
- CLI argument parsing and exit codes
