# Review App

A command line app that can be run with docker.  Built with python, this app will review a checklist stored either locally in .checklist or via a path set by an env var "REPO_CHECKLIST".  When run with Docker, this can be passed in on a volume mount with env var.  The checklist will be a markdown of rules for the LLM to check against this given code base.

## Example

A sample `.checklist` might be:
```
1. ensure every commit mentions a Vikunja ticket.  These start with "#nnn" where n is positive number
2. ensure every commit has a committer
3. check that the README.md is up to date
```

## Quick Start & Setup

The application supports **Vertex AI (Gemini)** or **Ollama** backends and requires one of them to be configured via environment variables:

- **Gemini / Vertex AI:** Set `GEMINI_KEY` and `GEMINI_MODEL`
- **Ollama:** Set `OLLAMA_URL` and `OLLAMA_MODEL`

For detailed setup instructions, Docker commands, volume mounting examples, and configuration options, see [SETUP.md](file:///home/isaac/Workspaces/reviewApp/SETUP.md).





