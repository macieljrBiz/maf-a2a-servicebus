# Future: Native MAF A2A Integration

This document describes a future migration path from the current Azure Service Bus transport to the **A2A (Agent-to-Agent) protocol** built into Microsoft Agent Framework (MAF). The A2A approach offers significant architectural advantages, but the required package (`agent-framework-a2a`) is still in **preview** as of April 2026. The current Service Bus implementation remains the recommended choice for stability.

---

## Current Architecture (Service Bus)

```
Client ──HTTP POST──▶ Orchestrator (FastAPI)
                          │
                          ├─ 1. Invoke Primary Agent (MAF → Azure OpenAI)
                          ├─ 2. Publish to Service Bus topic "agent-requests"
                          ├─ 3. Poll Service Bus queue "agent-responses" (120s timeout)
                          │
                          │         Service Bus
                          │     ┌────────────────────┐
                          └────▶│ topic: agent-requests│──▶ Partner Agent (SB consumer loop)
                                │ queue: agent-responses│◀── Partner Agent publishes response
                                └────────────────────┘
```

**Key characteristics:**
- Partner Agent is a headless Service Bus consumer loop (no HTTP server)
- Correlation is manual (`correlation_id` matching on the response queue)
- Requires Azure Service Bus namespace (Standard tier) with topic, subscription, and queue
- No streaming support — the Orchestrator polls the queue until a matching response arrives

---

## Target Architecture (A2A)

```
Client ──HTTP POST──▶ Orchestrator (FastAPI)
                          │
                          ├─ 1. Invoke Primary Agent (MAF → Azure OpenAI)
                          ├─ 2. Call Partner Agent via A2A (HTTP/JSON-RPC)
                          │         ▼
                          │     Partner Agent (A2A server)
                          │     ├─ /.well-known/agent.json (Agent Card)
                          │     └─ JSON-RPC endpoint (Starlette + uvicorn)
                          │              │
                          │              └─ Invoke Partner Agent (MAF → Azure OpenAI)
                          │              └─ Return response via A2A protocol
                          │         ▲
                          └─ 3. Receive Partner analysis from A2A response
```

**Key characteristics:**
- Partner Agent becomes an A2A-compliant HTTP server with self-describing Agent Card
- Orchestrator calls Partner Agent directly via `A2AAgent` client — no message broker
- Correlation is handled automatically by the A2A protocol (task IDs)
- SSE streaming is built-in
- No Azure Service Bus needed

---

## What is A2A?

A2A is an open protocol ([a2a-protocol.org](https://a2a-protocol.org/latest/)) that standardizes agent-to-agent communication. It supports:

- **Agent discovery** — each agent publishes an Agent Card at `/.well-known/agent.json` describing its name, skills, supported modes, and capabilities
- **Message-based communication** — JSON-RPC over HTTP
- **Streaming** — real-time updates via Server-Sent Events (SSE)
- **Long-running tasks** — continuation tokens for polling or resubscribing
- **Cross-framework interoperability** — any A2A-compliant agent can communicate, regardless of the framework it was built with

MAF provides two packages for A2A:

| Package | Role | Status |
|---|---|---|
| `agent-framework-a2a` | **Client** — wraps remote A2A endpoints as MAF agents (`A2AAgent`) | Preview (`--pre`) |
| `a2a-sdk` | **Server** — provides `A2AStarletteApplication`, `AgentExecutor`, request handlers, and A2A types | Stable |

---

## Migration Scope

### Partner Agent (`app-partner-agent/`)

This is the most impacted component. It transforms from a headless Service Bus consumer into an A2A HTTP server.

**Remove:**
- `azure-servicebus` dependency
- `ServiceBusClient` / `ServiceBusMessage` imports
- `send_to_queue()` function
- `receiver_loop()` — the infinite SB polling loop
- SB message parsing logic in `handle_message()`

**Keep as-is:**
- `PARTNER_AGENT_SYSTEM_PROMPT` and all simulated data
- MAF agent invocation (`OpenAIChatClient` + `as_agent()` + `agent.run()`)
- `upload_log()` (Blob Storage logging)

**Add:**
- `AgentFrameworkExecutor` class — bridges A2A protocol requests to the MAF agent (~50 lines, follows the [official MAF pattern](https://github.com/microsoft/agent-framework/blob/main/python/samples/04-hosting/a2a/agent_executor.py))
- `AgentCard` definition — declares the Partner Agent's identity, skills, and capabilities (~20 lines)
- `A2AStarletteApplication` + `uvicorn` entrypoint — replaces `asyncio.run(receiver_loop())` (~20 lines)

**New dependencies:**
```toml
dependencies = [
    "agent-framework",
    "agent-framework-openai",
    "a2a-sdk",          # A2A server components (stable)
    "azure-identity",
    "azure-storage-blob",
    "uvicorn",
    "python-dotenv",
]
```

**Entrypoint changes:**
```python
# Before (Service Bus consumer)
if __name__ == "__main__":
    asyncio.run(receiver_loop())

# After (A2A HTTP server)
if __name__ == "__main__":
    uvicorn.run(a2a_app.build(), host="0.0.0.0", port=8072)
```

The Partner Agent would expose its Agent Card at `http://localhost:8072/.well-known/agent.json`.

### Orchestrator (`app-orchestrator/`)

Moderate impact — replaces ~70 lines of Service Bus producer/consumer code with ~10 lines of A2AAgent client.

**Remove:**
- `azure-servicebus` dependency
- `ServiceBusClient` / `ServiceBusMessage` imports
- `_parse_sb_message()`, `send_to_topic()`, `receive_from_queue()` functions
- Steps 2–3 in the `orchestrator()` endpoint (publish to SB topic + poll SB queue)

**Keep as-is:**
- Primary Agent invocation (Step 1)
- Final response composition (Step 4)
- FastAPI server, `/api/ask` endpoint, logging, `upload_log()`

**Replace Steps 2–3 with:**
```python
from agent_framework.a2a import A2AAgent

partner_url = os.environ["PARTNER_AGENT_A2A_URL"]
async with A2AAgent(name="PartnerAgent", url=partner_url) as partner:
    response = await partner.run(prompt)
    partner_analysis = response.messages[0].text
```

**New dependencies:**
```toml
dependencies = [
    "agent-framework",
    "agent-framework-openai",
    "agent-framework-a2a",  # A2A client (preview)
    "azure-identity",
    "azure-storage-blob",
    "fastapi",
    "uvicorn",
    "python-dotenv",
]
```

### Client (`client/`)

**No changes.** The client only communicates with the Orchestrator via HTTP `POST /api/ask`.

### Environment (`.env`)

```diff
- SERVICEBUS_NAMESPACE=sbns-demo-orchestrator.servicebus.windows.net
+ PARTNER_AGENT_A2A_URL=http://localhost:8072
```

All other variables (Storage Account, Azure OpenAI endpoints, model deployments) remain unchanged.

---

## Benefits of A2A

| Benefit | Details |
|---|---|
| **Simpler local development** | No Azure Service Bus dependency — both agents run as HTTP servers on localhost |
| **Agent discovery** | Partner Agent is self-describing via its Agent Card |
| **Built-in streaming** | SSE support out of the box, vs. impossible with queue polling |
| **Cross-framework interop** | Any A2A-compliant client can invoke the Partner Agent, regardless of framework |
| **Cross-tenant ready** | Standard HTTPS + OAuth 2.0 authentication — no shared Azure infrastructure needed across tenants |
| **Fewer Azure resources** | Eliminates Service Bus namespace (topic, subscription, queue) — reduces cost and operational complexity |
| **Cleaner code** | ~70 lines of SB boilerplate in the Orchestrator collapse to ~10 lines of A2AAgent client code |
| **Standard protocol** | Built on the open A2A specification, not tied to a proprietary transport |

### Cross-Tenant Scenario

A2A is particularly advantageous when agents belong to different organizations (tenants). With Service Bus, cross-tenant access requires complex RBAC federation or shared connection strings. With A2A:

- Each organization hosts its own A2A agent on its own infrastructure
- Communication is standard HTTPS — firewalls, API gateways, and WAFs work naturally
- Authentication uses standard OAuth 2.0 `Bearer` tokens via `AuthInterceptor`
- No shared Azure resources are needed between tenants
- Data sovereignty is preserved — each agent controls what it exposes

---

## Trade-offs

| Consideration | Service Bus (current) | A2A (future) |
|---|---|---|
| **Durable messaging** | Messages persist in the broker; consumers can be offline | Requests are lost if the Partner Agent is down |
| **Dead-letter queue** | Built-in poison message handling | No equivalent — must be implemented at the application level |
| **Retry / back-pressure** | Configurable retry policies, message lock, abandon/complete semantics | Application-level retry (e.g., `httpx` retry, or background=True with polling) |
| **Offline consumers** | Partner Agent can restart and pick up queued messages | Partner Agent must be running to receive requests |
| **Package maturity** | `azure-servicebus` is GA and production-hardened | `agent-framework-a2a` is preview (`1.0.0b260409`) with potential breaking changes |
| **Throughput at scale** | Service Bus handles high-volume, bursty workloads natively | HTTP/JSON-RPC is synchronous by default; scaling requires load balancers |

For a **demo or proof-of-concept**, these trade-offs overwhelmingly favor A2A. For **production** workloads that require guaranteed delivery, the Service Bus approach (or a hybrid) may still be appropriate.

---

## Why We Keep Service Bus for Now

1. **Preview status** — `agent-framework-a2a` is `1.0.0b260409` (beta). The API surface may change before GA, and production support is not guaranteed.
2. **Proven reliability** — `azure-servicebus` is a mature, GA SDK with well-understood retry, dead-letter, and session semantics.
3. **Demo stability** — the current implementation has been end-to-end tested and is known to work. Switching to a preview package introduces risk for live demonstrations.
4. **Scope control** — the demo focuses on multi-agent orchestration patterns, not transport protocol evaluation.

**Recommendation:** Monitor `agent-framework-a2a` for GA release, then migrate. The server-side `a2a-sdk` package is already stable, so the Partner Agent's A2A server implementation is ready today — the blocker is only the client-side preview package used by the Orchestrator.

---

## Running the Demo After Migration

Once migrated, the demo startup sequence would change:

```
# Terminal 1 — Start Partner Agent (A2A server)
cd sample/app-partner-agent
uv sync --python 3.12
uv run python main.py
# → A2A server listening on http://localhost:8072
# → Agent Card at http://localhost:8072/.well-known/agent.json

# Terminal 2 — Start Orchestrator
cd sample/app-orchestrator
uv sync --python 3.12
uv run python main.py
# → FastAPI server on http://localhost:7071

# Terminal 3 — Run Client
cd sample/client
uv sync --python 3.12
uv run python main.py
```

The Partner Agent must be started **before** the Orchestrator sends requests (no queue buffering).

---

## References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/)
- [MAF A2A Integration Docs](https://learn.microsoft.com/en-us/agent-framework/integrations/a2a?pivots=programming-language-python)
- [MAF A2A Hosting Sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/a2a)
- [agent-framework-a2a on PyPI](https://pypi.org/project/agent-framework-a2a/)
- [a2a-sdk on PyPI](https://pypi.org/project/a2a-sdk/)
