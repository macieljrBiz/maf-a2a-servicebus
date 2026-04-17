# Service Bus vs A2A Protocol — Comparison

> **Author:** Vicente Maciel Junior — vicentem@microsoft.com — Cloud & AI Solutions Architect

This document compares the two inter-agent communication approaches evaluated for this project: **Azure Service Bus** (the original implementation) and the **A2A (Agent-to-Agent) protocol** (the current implementation).

---

## Architecture Overview

### Previous: Azure Service Bus

```
Orchestrator                          Partner Agent
  ├─ Publish request to SB topic       ← Subscribe to SB topic
  ├─ Poll SB response queue (120s)     ← Publish response to SB queue
  └─ Combine & return                  └─ Headless SB consumer loop
          │
     Azure Service Bus (Standard tier)
     ├─ Topic: agent-requests
     ├─ Subscription: partner-agent-sub
     └─ Queue: agent-responses
```

### Current: A2A Protocol

```
Orchestrator                          Partner Agent
  ├─ Resolve Agent Card (HTTP GET)      ← Serve Agent Card at /.well-known/agent.json
  ├─ Send A2A request (JSON-RPC)        ← Receive & process A2A request
  ├─ Receive A2A response               ← Return analysis via A2A response
  └─ Combine & return                   └─ A2A HTTP server (Starlette + uvicorn)
          │
     Direct HTTP (localhost:8072)
     No middleware required
```

---

## Side-by-Side Comparison

| Dimension | Azure Service Bus | A2A Protocol |
|---|---|---|
| **Infrastructure** | Requires Azure Service Bus namespace (Standard tier), topic, subscription, and queue | Zero additional infrastructure — agents communicate directly via HTTP |
| **Azure Resources** | 4 resources: namespace, topic, subscription, queue + RBAC role assignment | None — communication is peer-to-peer |
| **Setup Commands** | ~8 `az` CLI commands (namespace, topic, subscription, queue, RBAC) | 0 — just start both applications |
| **Cost** | ~$10/month (Standard tier minimum) + per-message charges | $0 additional cost |
| **Authentication** | `DefaultAzureCredential` → Service Bus RBAC (`Azure Service Bus Data Owner`) | None for localhost; TLS + mutual auth in production |
| **Code Complexity (Orchestrator)** | ~70 lines: `send_to_topic()`, `receive_from_queue()`, `_parse_sb_message()`, 120s polling loop | ~15 lines: `A2ACardResolver` + `A2AAgent.run()` |
| **Code Complexity (Partner Agent)** | ~50 lines: async `ServiceBusClient` receiver loop, message parsing, response queue publish | ~60 lines: `PartnerAgentExecutor`, `A2AStarletteApplication`, Agent Card definition |
| **Dependencies** | `azure-servicebus` (7.x) | `agent-framework-a2a` (preview) + `a2a-sdk` + `httpx` |
| **Protocol** | AMQP 1.0 (proprietary Azure protocol) | JSON-RPC over HTTP (open standard) |
| **Service Discovery** | Manual configuration (topic/queue names in code) | Automatic via Agent Card at `/.well-known/agent.json` |
| **Partner Agent Runtime** | Headless consumer loop (no HTTP server) | HTTP server with standard endpoints |
| **Cross-Framework Interop** | Partners must use Azure Service Bus SDK | Partners can use any framework that implements A2A |
| **Local Dev Experience** | Requires `az login` + Service Bus namespace + RBAC | Just `uv run python main.py` for each app |
| **Startup Time (Dev)** | ~30 minutes (Azure resource provisioning + RBAC propagation) | ~30 seconds (start two Python processes) |
| **Testing Workflow** | 3 terminals (Partner Agent → Orchestrator → Client) | 3 terminals (Partner Agent → Orchestrator → Client) — **unchanged** |

---

## Benefits of the A2A Migration

### 1. Eliminated Infrastructure Overhead

The Azure Service Bus namespace required:
- Standard tier ($10/month minimum even with no traffic)
- 4 resources to create and manage (namespace, topic, subscription, queue)
- RBAC role assignment (`Azure Service Bus Data Owner`)
- ~8 Azure CLI commands in the setup guide

With A2A, there is **zero Azure infrastructure** for inter-agent communication. The only Azure resources remaining are Storage Account (logging) and Azure OpenAI (LLM).

### 2. Simplified Developer Experience

| Task | Service Bus | A2A |
|---|---|---|
| First-time setup | Create Azure resources, assign RBAC, wait for propagation | None |
| Start Partner Agent | Must have valid `az login` and SB access | Just run the Python app |
| Debug communication | Azure Portal → Service Bus → Messages | Standard HTTP debugging (curl, browser, Fiddler) |
| Error diagnosis | Parse AMQP errors, check RBAC, verify topic/subscription | Standard HTTP status codes |

### 3. Reduced Code Complexity

The Service Bus implementation required:
- `send_to_topic()` — serialize and publish to topic
- `receive_from_queue()` — poll with 120s timeout, handle no-message case
- `_parse_sb_message()` — deserialize and extract partner response
- Async `ServiceBusClient` setup with `DefaultAzureCredential`
- Manual correlation ID threading through SB message properties

The A2A implementation replaces all of this with:
- `A2ACardResolver` to discover the Partner Agent
- `A2AAgent.run()` to call the Partner Agent (one line)
- Built-in task ID traceability (provided by the A2A protocol)

### 4. Open Standard Protocol

A2A is an [open specification](https://google.github.io/A2A/) that enables cross-framework interoperability:
- Partners are **not locked into Azure SDKs** — any HTTP server implementing A2A can participate
- **Agent Cards** provide self-describing service discovery (name, skills, capabilities)
- The protocol is **transport-agnostic** — works over any HTTP connection
- Multiple AI frameworks already support A2A (MAF, LangChain, CrewAI, etc.)

### 5. Preserved Testing Workflow

The 3-terminal testing workflow is **identical** in both approaches:

```
Terminal 1: cd sample/app-partner-agent && uv run python main.py
Terminal 2: cd sample/app-orchestrator && uv run python main.py
Terminal 3: cd sample/client && uv run python main.py
```

The only difference is the Partner Agent startup message:
- Service Bus: `Partner Agent started — waiting for messages on Service Bus`
- A2A: `Partner Agent A2A server starting...` → `Uvicorn running on http://localhost:8072`

---

## When Service Bus Is Still the Right Choice

A2A is ideal for this demo and many production scenarios, but Azure Service Bus provides capabilities that A2A alone does not:

| Capability | Service Bus | A2A |
|---|---|---|
| **Durable messaging** | Messages persist in queues even if the consumer is offline | Consumer must be online to receive requests |
| **Dead-letter queue** | Failed messages are automatically moved to DLQ for investigation | No built-in failure queue |
| **Guaranteed delivery** | At-least-once delivery with sessions and locks | HTTP request/response — no delivery guarantee beyond TCP |
| **Retry policies** | Built-in exponential backoff, max delivery count | Must implement retry logic in application code |
| **Offline partners** | Partners can process messages when they come back online | Partners must be reachable when the request is made |
| **High-volume bursts** | Handles thousands of messages/second with built-in buffering | Each request is a synchronous HTTP call |
| **Audit trail** | Azure Monitor integration, message diagnostics | Must implement logging separately |

### Recommended Hybrid Approach (Production)

For production architectures where both **simplicity** and **durability** are needed:

1. Use **A2A** as the primary protocol for real-time, synchronous agent-to-agent communication.
2. Layer **Azure Service Bus** as a transport for scenarios requiring:
   - Offline partner support (partners in different time zones or with maintenance windows)
   - Guaranteed delivery (regulatory requirements, financial transactions)
   - High-volume burst handling (campaign launches, peak periods)
3. Use the A2A Agent Card for **service discovery** regardless of the underlying transport.

This hybrid gives the best of both worlds: A2A's simplicity and interoperability for normal operation, with Service Bus's durability guarantees when the business requires them.

---

## Migration Summary

| Aspect | Before (Service Bus) | After (A2A) |
|---|---|---|
| `sample/app-orchestrator/main.py` | `send_to_topic()` + `receive_from_queue()` + polling loop | `A2ACardResolver` + `A2AAgent.run()` |
| `sample/app-partner-agent/main.py` | `ServiceBusClient` receiver loop | `A2AStarletteApplication` + `PartnerAgentExecutor` |
| `sample/app-orchestrator/pyproject.toml` | `azure-servicebus` | `agent-framework-a2a` + `a2a-sdk` + `httpx` |
| `sample/app-partner-agent/pyproject.toml` | `azure-servicebus` | `a2a-sdk` + `uvicorn` |
| `sample/.env` | `SERVICEBUS_NAMESPACE=sbns-demo-orchestrator.servicebus.windows.net` | `PARTNER_AGENT_A2A_URL=http://localhost:8072` |
| Azure resources | Storage + OpenAI + **Service Bus** | Storage + OpenAI |
| Setup commands | ~15 `az` commands | ~7 `az` commands (SB commands eliminated) |
| Total Azure cost (demo) | ~$10/month (SB) + OpenAI usage | OpenAI usage only |
