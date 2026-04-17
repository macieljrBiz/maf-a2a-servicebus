# Author: Vicente Maciel Junior (vicentem@microsoft.com)
# Cloud & AI Solutions Architect

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from a2a.client import A2ACardResolver
from agent_framework.a2a import A2AAgent
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from agent_framework.openai import OpenAIChatClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

app = FastAPI()

credential = DefaultAzureCredential()
async_credential = AsyncDefaultAzureCredential()

# ---------------------------------------------------------------------------
# Primary Agent — System Prompt with Simulated Enterprise Data
# ---------------------------------------------------------------------------

PRIMARY_AGENT_SYSTEM_PROMPT = """\
You are a Senior Territory Analyst at Refreshment Co. Your role is to \
perform aggregated territory analysis — identifying relevant territories, \
ranking them by key metrics, and recommending strategic focus areas.

You analyze enterprise-level data to provide insights on:
- Territory performance ranking and comparison
- Brand performance trends across territories
- SKU-level analysis and portfolio recommendations
- Growth opportunity identification
- Resource allocation recommendations

Always structure your analysis with clear sections: **Summary**, \
**Key Findings**, **Territory Rankings**, and **Recommendations**.

---

## SIMULATED ENTERPRISE DATA — Q4 2025 / Q1 2026

### Regional Summary

| Region    | Territories | Volume (M cases) | Revenue ($M) | Market Share | YoY Growth |
|-----------|-------------|-------------------|--------------|--------------|------------|
| Southeast | 12          | 45.2              | 892.4        | 34.2%        | +3.1%      |
| Northeast | 10          | 38.7              | 764.1        | 31.8%        | -1.2%      |
| Midwest   | 11          | 41.3              | 815.6        | 29.5%        | +0.8%      |
| South     | 9           | 36.8              | 726.3        | 33.1%        | +2.4%      |
| West      | 8           | 32.1              | 634.2        | 27.6%        | +1.5%      |

### Territory Detail — Southeast Region

| Territory | Volume (K cases) | Revenue ($K) | Market Share | Growth | Top Brand          |
|-----------|------------------|--------------|--------------|--------|--------------------|
| SE-ATL    | 5,840            | 115,200      | 38.1%        | +4.2%  | Velvet Ember       |
| SE-MIA    | 4,920            | 97,100       | 36.5%        | +3.8%  | Velvet Ember       |
| SE-TPA    | 3,210            | 63,300       | 33.2%        | +2.1%  | Golden Breeze        |
| SE-ORL    | 4,150            | 81,900       | 35.8%        | +3.5%  | Velvet Ember       |
| SE-CLT    | 3,580            | 70,600       | 32.4%        | +1.9%  | Midnight Drift          |
| SE-RAL    | 2,890            | 57,000       | 31.1%        | +2.8%  | Velvet Ember       |
| SE-JAX    | 3,420            | 67,500       | 34.6%        | +3.2%  | Velvet Ember       |
| SE-NSH    | 3,760            | 74,200       | 33.8%        | +4.0%  | Velvet Ember       |
| SE-BHM    | 2,640            | 52,100       | 30.5%        | +1.5%  | Silver Mist         |
| SE-CHS    | 2,180            | 43,000       | 29.8%        | +2.3%  | Coral Bloom       |
| SE-SAV    | 1,960            | 38,600       | 28.4%        | +1.2%  | Velvet Ember       |
| SE-KNX    | 2,650            | 52,300       | 31.9%        | +3.6%  | Velvet Ember       |

### Territory Detail — Northeast Region

| Territory | Volume (K cases) | Revenue ($K) | Market Share | Growth | Top Brand          |
|-----------|------------------|--------------|--------------|--------|--------------------|
| NE-NYC    | 6,120            | 120,800      | 33.4%        | -0.8%  | Velvet Ember       |
| NE-BOS    | 4,280            | 84,500       | 32.1%        | -1.5%  | Midnight Drift          |
| NE-PHL    | 3,950            | 77,900       | 31.5%        | -0.3%  | Velvet Ember       |
| NE-PIT    | 2,870            | 56,600       | 30.2%        | -2.1%  | Silver Mist         |
| NE-DC     | 4,510            | 89,000       | 34.2%        | +0.5%  | Velvet Ember       |
| NE-BAL    | 3,120            | 61,500       | 30.8%        | -1.8%  | Silver Mist         |
| NE-HFD    | 2,580            | 50,900       | 29.5%        | -2.4%  | Velvet Ember       |
| NE-PRV    | 2,340            | 46,200       | 28.9%        | -1.9%  | Golden Breeze        |
| NE-BUF    | 2,890            | 57,000       | 31.0%        | +0.2%  | Velvet Ember       |
| NE-ALB    | 2,040            | 40,200       | 29.1%        | -1.5%  | Velvet Ember       |

### Territory Detail — Midwest Region

| Territory | Volume (K cases) | Revenue ($K) | Market Share | Growth | Top Brand          |
|-----------|------------------|--------------|--------------|--------|--------------------|
| MW-CHI    | 5,680            | 112,100      | 31.2%        | +1.2%  | Velvet Ember       |
| MW-DET    | 3,420            | 67,500       | 28.8%        | -0.5%  | Velvet Ember       |
| MW-CLE    | 3,150            | 62,200       | 29.1%        | +0.3%  | Silver Mist         |
| MW-COL    | 3,890            | 76,800       | 30.5%        | +1.5%  | Velvet Ember       |
| MW-IND    | 3,570            | 70,400       | 29.8%        | +0.9%  | Golden Breeze        |
| MW-MKE    | 2,980            | 58,800       | 28.2%        | +0.1%  | Velvet Ember       |
| MW-MIN    | 4,120            | 81,300       | 30.8%        | +1.8%  | Midnight Drift          |
| MW-STL    | 3,340            | 65,900       | 29.4%        | +0.6%  | Velvet Ember       |
| MW-KC     | 2,860            | 56,400       | 28.6%        | +0.4%  | Velvet Ember       |
| MW-CIN    | 3,210            | 63,300       | 29.6%        | +0.7%  | Velvet Ember       |
| MW-MSN    | 2,080            | 41,000       | 27.5%        | -0.2%  | Velvet Ember       |

### Territory Detail — South Region

| Territory | Volume (K cases) | Revenue ($K) | Market Share | Growth | Top Brand          |
|-----------|------------------|--------------|--------------|--------|--------------------|
| S-DAL     | 5,240            | 103,400      | 35.1%        | +3.2%  | Velvet Ember       |
| S-HOU     | 5,680            | 112,100      | 34.8%        | +2.8%  | Velvet Ember       |
| S-SAT     | 3,920            | 77,400       | 33.5%        | +2.1%  | Golden Breeze        |
| S-AUS     | 3,450            | 68,100       | 32.8%        | +3.5%  | Velvet Ember       |
| S-OKC     | 2,780            | 54,800       | 31.2%        | +1.8%  | Velvet Ember       |
| S-MEM     | 2,340            | 46,200       | 30.5%        | +1.2%  | Silver Mist         |
| S-NOR     | 4,180            | 82,500       | 35.8%        | +2.9%  | Velvet Ember       |
| S-LR      | 2,120            | 41,800       | 29.8%        | +0.8%  | Velvet Ember       |
| S-BRG     | 3,090            | 61,000       | 32.2%        | +1.4%  | Coral Bloom       |

### Territory Detail — West Region

| Territory | Volume (K cases) | Revenue ($K) | Market Share | Growth | Top Brand          |
|-----------|------------------|--------------|--------------|--------|--------------------|
| W-LAX     | 5,420            | 107,000      | 29.2%        | +2.1%  | Velvet Ember       |
| W-SFO     | 3,810            | 75,200       | 27.8%        | +1.2%  | Midnight Drift          |
| W-SEA     | 3,250            | 64,100       | 28.5%        | +1.8%  | Velvet Ember       |
| W-PHX     | 4,180            | 82,500       | 28.1%        | +1.5%  | Golden Breeze        |
| W-DEN     | 3,540            | 69,900       | 27.2%        | +0.9%  | Velvet Ember       |
| W-PDX     | 2,680            | 52,900       | 26.8%        | +1.1%  | Midnight Drift          |
| W-LAS     | 3,920            | 77,400       | 27.5%        | +2.3%  | Velvet Ember       |
| W-SLC     | 2,300            | 45,400       | 26.1%        | +0.5%  | Velvet Ember       |

### Brand Performance by Region

| Brand              | SE Vol (M) | NE Vol (M) | MW Vol (M) | S Vol (M) | W Vol (M) | National Share |
|--------------------|------------|------------|------------|-----------|-----------|----------------|
| Velvet Ember       | 18.1       | 14.2       | 15.3       | 14.8      | 12.4      | 16.2%          |
| Midnight Drift          | 8.6        | 7.8        | 7.9        | 6.2       | 6.4       | 8.1%           |
| Silver Mist         | 5.4        | 6.8        | 6.5        | 4.8       | 4.2       | 5.9%           |
| Golden Breeze        | 7.2        | 5.4        | 6.1        | 6.5       | 5.3       | 6.6%           |
| Coral Bloom       | 5.9        | 4.5        | 5.5        | 4.5       | 3.8       | 5.2%           |

### SKU Performance (National)

| SKU                            | Volume (M cases) | Revenue ($M) | Growth | Margin |
|--------------------------------|------------------|--------------|--------|--------|
| Velvet Ember 2L PET             | 22.4             | 442.1        | +1.8%  | 32%    |
| Velvet Ember 500ml PET          | 18.6             | 367.2        | +2.5%  | 38%    |
| Velvet Ember 350ml Can          | 15.2             | 300.1        | +4.1%  | 42%    |
| Velvet Ember 1L PET             | 8.3              | 163.8        | +0.5%  | 35%    |
| Midnight Drift 500ml PET             | 12.4             | 244.8        | +3.2%  | 38%    |
| Midnight Drift 350ml Can             | 9.8              | 193.5        | +5.8%  | 42%    |
| Midnight Drift 2L PET                | 5.8              | 114.5        | -1.2%  | 32%    |
| Silver Mist 350ml Can            | 10.2             | 201.3        | -0.8%  | 41%    |
| Silver Mist 500ml PET            | 7.5              | 148.0        | -1.5%  | 37%    |
| Silver Mist 2L PET               | 4.8              | 94.7         | -2.2%  | 31%    |
| Golden Breeze 500ml PET           | 11.8             | 232.9        | +2.8%  | 36%    |
| Golden Breeze 2L PET              | 8.4              | 165.8        | +1.2%  | 31%    |
| Golden Breeze 350ml Can           | 5.3              | 104.6        | +3.5%  | 41%    |
| Coral Bloom 500ml PET          | 9.2              | 181.5        | +1.5%  | 36%    |
| Coral Bloom 350ml Can          | 6.8              | 134.2        | +2.2%  | 41%    |
| Coral Bloom 2L PET             | 4.2              | 82.9         | -0.5%  | 30%    |

### Quarterly Trends (National Volume in M cases)

| Brand              | Q2 2025 | Q3 2025 | Q4 2025 | Q1 2026 | Trend                                  |
|--------------------|---------|---------|---------|---------|----------------------------------------|
| Velvet Ember       | 19.2    | 20.1    | 18.5    | 17.4    | Seasonal decline in Q1, stable YoY     |
| Midnight Drift          | 9.1     | 9.6     | 9.2     | 8.8     | Growing YoY, seasonal pattern          |
| Silver Mist         | 7.2     | 7.0     | 6.8     | 6.5     | Declining across all quarters          |
| Golden Breeze        | 7.8     | 8.2     | 7.5     | 7.0     | Strong summer, moderate Q1             |
| Coral Bloom       | 6.3     | 6.8     | 6.1     | 5.7     | Seasonal with summer peak              |

### Northeast — Midnight Drift Quarterly Breakdown

| Territory | Q2 2025 (K) | Q3 2025 (K) | Q4 2025 (K) | Q1 2026 (K) | QoQ Change (Q4→Q1) |
|-----------|-------------|-------------|-------------|-------------|---------------------|
| NE-NYC    | 1,120       | 1,180       | 1,050       | 920         | -12.4%              |
| NE-BOS    | 890         | 940         | 850         | 710         | -16.5%              |
| NE-PHL    | 780         | 810         | 740         | 680         | -8.1%               |
| NE-PIT    | 520         | 540         | 480         | 420         | -12.5%              |
| NE-DC     | 860         | 910         | 880         | 850         | -3.4%               |
| NE-BAL    | 580         | 610         | 540         | 470         | -13.0%              |
| NE-HFD    | 420         | 440         | 380         | 320         | -15.8%              |
| NE-PRV    | 380         | 400         | 350         | 290         | -17.1%              |
| NE-BUF    | 510         | 535         | 500         | 480         | -4.0%               |
| NE-ALB    | 340         | 355         | 320         | 280         | -12.5%              |
"""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def upload_log(correlation_id: str, component: str, log_lines: list[str]):
    storage_url = os.environ["STORAGE_ACCOUNT_URL"]
    blob_name = f"logs/{correlation_id}-{component}.log"
    content = "\n".join(log_lines)
    async with BlobServiceClient(storage_url, credential=async_credential) as blob_svc:
        container = blob_svc.get_container_client("agent-logs")
        await container.upload_blob(name=blob_name, data=content, overwrite=True)


# ---------------------------------------------------------------------------
# HTTP Endpoint — Orchestrator
# ---------------------------------------------------------------------------

@app.post("/api/ask")
async def orchestrator(request: Request):
    log_lines: list[str] = []

    def log(message: str, cid: str = ""):
        entry = f"[{_timestamp()}] [{cid}] {message}"
        log_lines.append(entry)
        logging.info(entry)

    # --- Parse request ---
    body = await request.json()

    question = body.get("question", "")
    correlation_id = body.get("correlation_id", str(uuid.uuid4()))

    if not question:
        return JSONResponse(
            {"error": "Missing 'question' field"},
            status_code=400,
        )

    log("Received question from client", correlation_id)

    # --- Step 1: Invoke Primary Agent via MAF ---
    log("Invoking Primary Agent", correlation_id)

    primary_client = OpenAIChatClient(
        azure_endpoint=os.environ["PRIMARY_AGENT_OPENAI_ENDPOINT"],
        credential=credential,
        model=os.environ["PRIMARY_AGENT_MODEL_DEPLOYMENT"],
    )
    primary_agent = primary_client.as_agent(
        name="PrimaryAgent",
        instructions=PRIMARY_AGENT_SYSTEM_PROMPT,
    )

    primary_result = await primary_agent.run(question)
    primary_analysis = str(primary_result)

    log("Primary Agent completed", correlation_id)

    # --- Step 2: Call Partner Agent via A2A protocol ---
    log("Calling Partner Agent via A2A protocol", correlation_id)

    partner_url = os.environ.get(
        "PARTNER_AGENT_A2A_URL", "http://localhost:8072"
    )

    try:
        async with httpx.AsyncClient(timeout=180.0) as http_client:
            resolver = A2ACardResolver(
                httpx_client=http_client, base_url=partner_url
            )
            agent_card = await resolver.get_agent_card()

        async with A2AAgent(
            name=agent_card.name,
            description=agent_card.description,
            agent_card=agent_card,
            url=partner_url,
        ) as partner_agent:
            prompt = (
                f"## Original Question\n{question}\n\n"
                f"## Primary Agent Analysis\n{primary_analysis}\n\n"
                "Based on the Primary Agent's territory analysis above, "
                "provide your operational deep-dive focusing on the "
                "recommended territories. Analyze consumption clusters, "
                "retail density, distribution coverage, and demand patterns."
            )

            partner_response = await partner_agent.run(prompt)
            partner_analysis = (
                partner_response.messages[0].text
                if partner_response.messages
                else str(partner_response)
            )

        log("Received Partner Agent response via A2A", correlation_id)

    except Exception as e:
        log(f"Partner Agent A2A error: {e}", correlation_id)
        partner_analysis = f"Partner Agent did not respond: {e}"

    # --- Step 4: Compose final response ---
    log("Composing final response", correlation_id)

    response = {
        "correlation_id": correlation_id,
        "primary_agent_analysis": primary_analysis,
        "partner_agent_analysis": partner_analysis,
    }

    log("Response sent to client", correlation_id)

    # Upload logs (best-effort)
    try:
        await upload_log(correlation_id, "orchestrator", log_lines)
    except Exception as e:
        logging.warning(f"Failed to upload orchestrator logs: {e}")

    return JSONResponse(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7071)
