# Project Instructions

This is a **solution architecture analysis** project. The goal is to investigate, document, and discuss architectural decisions — not to generate code or artifacts automatically.

## Rules

- **Do not generate any artifact** (code, files, diagrams, templates, configurations, etc.) unless the user explicitly requests it.
- Focus on **analysis, explanation, and recommendation** regarding the solution architecture.
- When the user asks questions, respond with analyses, trade-offs, and technical justifications.
- Wait for explicit instructions before creating or modifying any file in the workspace.
- **All generated artifacts must be in English.**
- **All architecture diagrams must be generated in `.drawio` (Draw.io XML) format** using official Azure icon stencils (`mxgraph.azure.*`) when referencing Azure services.
- **Always use `uv` as the Python package manager.** Never use `pip`, `pip install`, or `pip freeze`. Use `uv sync` to install dependencies from `pyproject.toml`, `uv add <pkg>` to add a dependency, `uv run <script>` to execute scripts, and `uv pip install` only when targeting an existing venv that uv manages. All Python sub-projects use `pyproject.toml` with `[tool.uv] package = false` (they are not distributable packages).

## Sample Demo Planning

The project includes a minimal sample implementation under `sample/` to demonstrate the multi-agent orchestration pattern. Key decisions:

### Stack
- **Language**: Python
- **Package manager**: uv
- **Agent framework**: [Microsoft Agent Framework (MAF) 1.0](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python) — GA, successor to AutoGen and Semantic Kernel
  - Python packages: `agent-framework` (core) + `agent-framework-openai` (Azure OpenAI provider)
  - Agent class: `Agent` from `agent_framework` with `OpenAIChatCompletionClient` from `agent_framework.openai`
  - Azure OpenAI routing: pass `azure_endpoint` and `credential` (`DefaultAzureCredential`) to `OpenAIChatCompletionClient`
  - The old `AzureOpenAI*` compatibility classes were removed — always use `agent_framework.openai`
- **Orchestrator**: Python app with FastAPI + uvicorn (HTTP server, local execution)
- **Partner Agent**: Python app with async Service Bus receiver loop (local execution)
- **Messaging**: Azure Service Bus (Standard tier)
- **Logging**: Azure Storage Account (log files per execution)
- **LLM**: Azure OpenAI (separate deployment per agent)

### Architecture
- **Client** (`sample/client/`): Interactive Python CLI script.
- **Orchestrator** (`sample/app-orchestrator/`): MAF 1.0 orchestrator + Primary Agent. FastAPI HTTP server. Uses `Agent` + `OpenAIChatClient` with Azure routing.
- **Partner Agent** (`sample/app-partner-agent/`): Partner Agent. Async Service Bus receiver loop. Uses `Agent` + `OpenAIChatClient` with Azure routing.

### Use-Case Scenario
- **Input**: Free-text question from the user (no scenario selector).
- **Primary Agent**: Aggregated territory analysis — identifies relevant territories, ranks by key metrics, recommends focus areas.
- **Partner Agent**: Operational deep-dive — analyzes consumption clusters, retail density, distribution coverage, and demand patterns within recommended territories.
- **Simulated data**: No real data sources. Each agent's system prompt includes a comprehensive simulated dataset covering multiple regions, territories, brands, and SKUs.
- **Final output**: Orchestrator combines both analyses into a consolidated view.
- **Suggested test questions**:
  1. "Analyze the opportunity for launching a 350ml Classic Cola can in the Southeast region. Which territories show the highest potential based on current brand performance?"
  2. "Zero Cola has been declining in the Northeast region over the last two quarters. What's driving the drop, and which territories need immediate attention?"
  3. "We're rationalizing the product portfolio in the Midwest region. Which low-performing SKUs should we consider discontinuing, and what's the risk of losing shelf space?"
  4. "Summer peak is approaching. Based on last year's performance, which territories in the South region need increased distribution capacity for the Classic Cola 2L package?"

### Design Decisions (Demo)
- Plain Python apps instead of Azure Functions — removes runtime friction (extension bundles, embedded Python worker, PYTHONPATH issues) while preserving the same architectural pattern. Production should use Container Apps, App Service, or Functions with proper CI/CD.
- Synchronous polling on Service Bus response — demo simplification. Production should use event-driven processing.
- Single subscription with two resource groups simulates cross-organization boundaries.
- HITL and Auditor Agent are out of scope for this demo.
- Log files use correlation IDs and timestamps. No prompt or AI-generated content is logged.

### Configuration
All configuration is provided via `.env` files. Required values:
- Service Bus namespace (FQDN, no connection string)
- Storage Account URL (no connection string)
- Azure OpenAI endpoint for each agent (no API keys)
- Model deployment names
- All authentication uses `DefaultAzureCredential` (falls back to `az login` locally)
