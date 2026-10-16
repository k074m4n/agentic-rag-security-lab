"""
Templates for KB chapter tasks used by plan_kb_tasks_from_codebase.

These are plain Python format strings. Dynamic hints like dirs_hint or
config_hint are injected in kb_orchestration_toolkit.py.
"""

KB_OVERVIEW_TASK = """Analyze the entire codebase under '{codebase_path}' and write a high-level
overview markdown file named 'OVERVIEW.md'. Explain the main purpose of the project,
its primary entry points (for example app.py, main.py, or similar), and briefly
describe the top-level directories ({dirs_hint}). Include sections:
- Project purpose and high-level description
- Main entry points and how the application is started
- Top-level directory overview
- Very short "Getting started" instructions if you can infer them

Write the file into your workspace using write_workspace_file()."""

KB_ARCHITECTURE_TASK = """Infer the software architecture of the project and write 'ARCHITECTURE.md'.
Describe how the code is organized into modules or layers, and how requests or data
flow through the system. Include sections:
- High-level architecture overview
- Important modules / packages and their responsibilities
- How different parts of the system depend on each other
- Any external services, databases, or integrations you can detect

Use simple text diagrams (for example bullet lists or arrows) where helpful.
Write the file via write_workspace_file()."""

KB_API_REFERENCE_TASK = """If the project exposes any HTTP API, CLI commands, or other public interfaces,
analyze them and write 'API_REFERENCE.md'. {api_hint}
Include sections:
- Overview of the public API surface
- For HTTP APIs: method, path, and handler/function for each endpoint
- Important request parameters and response shapes
- Any authentication / authorization mechanisms you can infer

If you cannot find any clear API, explain that in the document and describe
any main entry functions or scripts instead. Write the file with write_workspace_file()."""

KB_DATA_MODELS_TASK = """Identify important data models and schemas in the project (for example ORM models,
Pydantic models, dataclasses, or other classes that hold structured data) and write
'DATA_MODELS.md'. Include sections:
- List of key models or schema classes with a short description
- Important fields/attributes for each model
- Any relationships between models (for example one-to-many, foreign keys)
- Where these models are used in the codebase

Write the file via write_workspace_file()."""

KB_BUILD_AND_TOOLING_TASK = """Examine the project's configuration, dependency, and tooling files and write
'BUILD_AND_TOOLING.md'. Pay attention to files such as requirements.txt,
pyproject.toml, package.json, Dockerfile, config.py, or CI/CD configurations.
Files detected during scanning: {config_hint}.
Include sections:
- Dependencies and how to install them
- How to run the application in development
- How to run tests or linting (if such commands are present)
- Any noteworthy tooling (formatters, linters, task runners, CI scripts)

Write the file using write_workspace_file()."""

KB_TESTING_AND_QA_TASK = """Analyze the tests and quality-related files in the project and write
'TESTING_AND_QA.md'. Look for {tests_hint}, as well as any QA or linting configuration.
Include sections:
- Where tests live in the repository and what they cover
- Types of tests present (unit, integration, end-to-end, etc.)
- Example important test cases
- Any quality gates, linters, or CI checks you can infer

Write the file via write_workspace_file()."""