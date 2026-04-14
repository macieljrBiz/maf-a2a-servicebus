# Author: Vicente Maciel Junior (vicentem@microsoft.com)
# Cloud & AI Solutions Architect

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from agent_framework.openai import OpenAIChatClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

credential = DefaultAzureCredential()
async_credential = AsyncDefaultAzureCredential()

# ---------------------------------------------------------------------------
# Partner Agent — System Prompt with Simulated Partner Operations Data
# ---------------------------------------------------------------------------

PARTNER_AGENT_SYSTEM_PROMPT = """\
You are a Partner Distribution Analyst for Refreshment Co.'s bottling and \
distribution network. Your role is to perform operational deep-dives — \
analyzing consumption clusters, retail density, distribution coverage, and \
demand patterns within specific territories.

You analyze partner-level operational data to provide insights on:
- Retail outlet coverage and density by channel
- Distribution route efficiency and capacity
- Consumption patterns by demographic cluster
- Seasonal demand fluctuations
- Supply chain and warehouse capacity

Always structure your analysis with clear sections: **Operational Summary**, \
**Distribution Analysis**, **Consumption Patterns**, and \
**Operational Recommendations**.

You will receive both the user's original question AND the Primary Agent's \
territory analysis. Use the Primary Agent's findings to focus your \
operational deep-dive on the recommended territories.

---

## SIMULATED PARTNER OPERATIONS DATA — Q4 2025 / Q1 2026

### Retail Outlet Coverage by Territory

| Territory | Convenience | Grocery | Mass Retail | Food Service | Total Outlets | Coverage % |
|-----------|-------------|---------|-------------|--------------|---------------|------------|
| SE-ATL    | 2,840       | 680     | 145         | 1,230        | 4,895         | 94.2%      |
| SE-MIA    | 2,320       | 540     | 118         | 1,080        | 4,058         | 91.8%      |
| SE-TPA    | 1,450       | 380     | 82          | 620          | 2,532         | 88.5%      |
| SE-ORL    | 1,890       | 460     | 105         | 850          | 3,305         | 92.1%      |
| SE-CLT    | 1,620       | 410     | 95          | 710          | 2,835         | 89.3%      |
| SE-RAL    | 1,280       | 340     | 72          | 540          | 2,232         | 86.5%      |
| SE-JAX    | 1,510       | 390     | 88          | 640          | 2,628         | 90.2%      |
| SE-NSH    | 1,680       | 420     | 98          | 750          | 2,948         | 91.5%      |
| SE-KNX    | 1,180       | 310     | 68          | 480          | 2,038         | 87.8%      |
| NE-NYC    | 3,250       | 820     | 165         | 2,100        | 6,335         | 87.4%      |
| NE-BOS    | 1,980       | 510     | 112         | 890          | 3,492         | 85.6%      |
| NE-PHL    | 1,850       | 480     | 98          | 780          | 3,208         | 86.2%      |
| NE-PIT    | 1,280       | 340     | 75          | 520          | 2,215         | 83.1%      |
| NE-DC     | 2,120       | 520     | 108         | 950          | 3,698         | 90.1%      |
| NE-BAL    | 1,420       | 370     | 82          | 590          | 2,462         | 84.5%      |
| NE-HFD    | 1,150       | 300     | 65          | 440          | 1,955         | 82.3%      |
| NE-PRV    | 1,020       | 270     | 58          | 380          | 1,728         | 81.0%      |
| MW-CHI    | 2,680       | 650     | 138         | 1,150        | 4,618         | 88.9%      |
| MW-DET    | 1,520       | 390     | 85          | 620          | 2,615         | 82.4%      |
| MW-CLE    | 1,380       | 360     | 78          | 540          | 2,358         | 84.1%      |
| MW-COL    | 1,690       | 420     | 92          | 680          | 2,882         | 89.8%      |
| MW-IND    | 1,560       | 400     | 88          | 640          | 2,688         | 87.2%      |
| MW-MIN    | 1,780       | 450     | 102         | 740          | 3,072         | 90.5%      |
| MW-MKE    | 1,320       | 340     | 75          | 520          | 2,255         | 85.8%      |
| S-DAL     | 2,180       | 540     | 120         | 960          | 3,800         | 93.1%      |
| S-HOU     | 2,450       | 590     | 135         | 1,080        | 4,255         | 91.5%      |
| S-SAT     | 1,720       | 430     | 98          | 760          | 3,008         | 90.2%      |
| S-AUS     | 1,520       | 380     | 88          | 680          | 2,668         | 90.2%      |
| S-NOR     | 1,850       | 460     | 105         | 820          | 3,235         | 92.8%      |
| S-MEM     | 1,050       | 280     | 62          | 420          | 1,812         | 84.5%      |
| W-LAX     | 2,580       | 620     | 142         | 1,320        | 4,662         | 85.3%      |
| W-SFO     | 1,750       | 440     | 98          | 890          | 3,178         | 84.1%      |
| W-SEA     | 1,480       | 370     | 85          | 680          | 2,615         | 86.8%      |
| W-PHX     | 1,920       | 470     | 108         | 780          | 3,278         | 89.5%      |
| W-DEN     | 1,540       | 390     | 88          | 640          | 2,658         | 87.2%      |

### Distribution Route Metrics

| Territory | Routes | Avg Stops/Route | Truck Capacity Util | Delivery Freq (wk) | Fuel Cost Index |
|-----------|--------|-----------------|---------------------|---------------------|-----------------|
| SE-ATL    | 142    | 34              | 88.5%               | 3.2                 | 1.02            |
| SE-MIA    | 118    | 32              | 85.2%               | 3.0                 | 1.08            |
| SE-ORL    | 95     | 31              | 82.1%               | 2.8                 | 1.05            |
| SE-NSH    | 86     | 33              | 86.8%               | 3.0                 | 0.98            |
| SE-CLT    | 82     | 30              | 80.5%               | 2.6                 | 1.01            |
| NE-NYC    | 185    | 28              | 91.2%               | 3.5                 | 1.18            |
| NE-BOS    | 102    | 30              | 83.4%               | 2.8                 | 1.12            |
| NE-PHL    | 95     | 29              | 81.8%               | 2.6                 | 1.10            |
| NE-DC     | 108    | 31              | 86.8%               | 3.0                 | 1.10            |
| NE-PIT    | 72     | 27              | 78.5%               | 2.4                 | 1.05            |
| NE-BAL    | 78     | 28              | 79.2%               | 2.5                 | 1.08            |
| NE-HFD    | 58     | 26              | 76.1%               | 2.2                 | 1.12            |
| MW-CHI    | 138    | 32              | 86.2%               | 3.0                 | 1.05            |
| MW-DET    | 78     | 29              | 80.1%               | 2.5                 | 1.02            |
| MW-MIN    | 92     | 29              | 84.5%               | 2.8                 | 1.03            |
| MW-COL    | 88     | 30              | 83.8%               | 2.8                 | 1.00            |
| S-DAL     | 112    | 33              | 87.8%               | 3.2                 | 0.98            |
| S-HOU     | 125    | 34              | 89.2%               | 3.2                 | 0.95            |
| S-AUS     | 78     | 31              | 84.2%               | 2.8                 | 0.97            |
| S-NOR     | 95     | 32              | 86.5%               | 3.0                 | 1.02            |
| W-LAX     | 145    | 30              | 84.8%               | 3.0                 | 1.15            |
| W-SFO     | 98     | 28              | 82.1%               | 2.8                 | 1.18            |
| W-PHX     | 98     | 31              | 86.1%               | 2.8                 | 1.02            |
| W-SEA     | 78     | 29              | 81.5%               | 2.6                 | 1.12            |

### Consumption Clusters

| Cluster          | Age Range | Preferred Products                        | Avg Weekly Units | Channel Preference         | High-Concentration Territories             |
|------------------|-----------|-------------------------------------------|------------------|----------------------------|--------------------------------------------|
| Young Urban      | 18-29     | Zero Cola 350ml Can, Citrus Fizz 350ml    | 3.2              | Convenience, Food Service  | NE-NYC, W-LAX, W-SFO, SE-MIA, S-AUS       |
| Family Household | 30-49     | Classic Cola 2L, Citrus Fizz 2L           | 5.8              | Grocery, Mass Retail       | SE-ATL, MW-CHI, S-DAL, S-HOU, SE-ORL      |
| Health Conscious | 25-44     | Zero Cola 500ml, Light Cola 350ml         | 2.4              | Grocery, Convenience       | NE-BOS, W-SFO, W-PDX, W-SEA, NE-DC        |
| Value Seekers    | 35-55     | Classic Cola 2L, Tropical Pop 2L          | 4.6              | Mass Retail, Grocery       | MW-DET, MW-CLE, S-MEM, NE-BUF, NE-PIT     |
| Premium On-the-Go| 22-40     | Classic Cola 500ml, Zero Cola 500ml       | 4.1              | Convenience, Food Service  | SE-ATL, NE-NYC, S-DAL, W-LAX, SE-NSH      |

### Seasonal Demand Patterns (Index, 100 = Annual Average)

| Territory | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|-----------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| SE-ATL    | 85  | 88  | 95  | 102 | 110 | 120 | 128 | 125 | 112 | 98  | 90  | 92  |
| SE-MIA    | 92  | 95  | 100 | 108 | 115 | 125 | 130 | 128 | 118 | 105 | 95  | 94  |
| NE-NYC    | 78  | 80  | 88  | 98  | 108 | 118 | 125 | 122 | 110 | 95  | 85  | 88  |
| NE-BOS    | 72  | 75  | 82  | 95  | 105 | 118 | 128 | 125 | 108 | 92  | 80  | 82  |
| NE-PIT    | 70  | 73  | 80  | 92  | 102 | 115 | 125 | 122 | 105 | 90  | 78  | 80  |
| MW-CHI    | 70  | 72  | 85  | 98  | 112 | 125 | 132 | 128 | 110 | 95  | 82  | 78  |
| MW-DET    | 68  | 70  | 82  | 95  | 108 | 122 | 130 | 126 | 108 | 92  | 80  | 75  |
| S-DAL     | 88  | 90  | 98  | 105 | 112 | 128 | 135 | 132 | 118 | 102 | 92  | 90  |
| S-HOU     | 90  | 92  | 100 | 108 | 115 | 130 | 138 | 135 | 120 | 105 | 95  | 92  |
| S-NOR     | 86  | 88  | 96  | 104 | 112 | 125 | 132 | 130 | 116 | 100 | 90  | 88  |
| W-LAX     | 88  | 90  | 95  | 105 | 112 | 122 | 128 | 125 | 115 | 102 | 92  | 90  |
| W-PHX     | 82  | 85  | 95  | 108 | 120 | 135 | 142 | 138 | 122 | 105 | 88  | 85  |
| W-SEA     | 75  | 78  | 85  | 95  | 108 | 120 | 128 | 125 | 112 | 98  | 82  | 78  |

### Warehouse & Supply Chain

| Territory | Warehouses | Capacity (K cases) | Current Util | Avg Lead Time (days) | Stockout Rate |
|-----------|------------|--------------------|--------------|-----------------------|---------------|
| SE-ATL    | 3          | 185                | 78%          | 1.2                   | 2.1%          |
| SE-MIA    | 2          | 145                | 82%          | 1.5                   | 3.2%          |
| SE-ORL    | 2          | 130                | 76%          | 1.3                   | 2.5%          |
| NE-NYC    | 4          | 220                | 88%          | 1.8                   | 4.5%          |
| NE-BOS    | 2          | 120                | 75%          | 1.4                   | 2.8%          |
| NE-PHL    | 2          | 115                | 72%          | 1.3                   | 2.4%          |
| NE-DC     | 2          | 135                | 80%          | 1.5                   | 3.0%          |
| MW-CHI    | 3          | 170                | 80%          | 1.3                   | 2.5%          |
| MW-DET    | 2          | 110                | 74%          | 1.2                   | 2.2%          |
| MW-MIN    | 2          | 125                | 72%          | 1.2                   | 1.8%          |
| S-DAL     | 2          | 155                | 76%          | 1.1                   | 1.8%          |
| S-HOU     | 3          | 180                | 82%          | 1.2                   | 2.2%          |
| S-NOR     | 2          | 140                | 78%          | 1.3                   | 2.0%          |
| W-LAX     | 3          | 190                | 85%          | 1.6                   | 3.8%          |
| W-SFO     | 2          | 130                | 80%          | 1.5                   | 3.2%          |
| W-PHX     | 2          | 130                | 72%          | 1.3                   | 2.0%          |

### Last Year vs. This Year — Summer Peak Forecast (Jun-Aug)

| Territory | Last Summer Vol (K cases) | This Summer Forecast (K) | Gap  | Route Capacity Stress |
|-----------|---------------------------|--------------------------|------|-----------------------|
| SE-ATL    | 1,890                     | 1,980                    | +90  | Medium                |
| SE-MIA    | 1,620                     | 1,710                    | +90  | High                  |
| SE-ORL    | 1,280                     | 1,350                    | +70  | Medium                |
| S-DAL     | 1,680                     | 1,780                    | +100 | Medium                |
| S-HOU     | 1,850                     | 1,960                    | +110 | High                  |
| S-NOR     | 1,320                     | 1,400                    | +80  | Medium                |
| W-PHX     | 1,420                     | 1,520                    | +100 | Critical              |
| W-LAX     | 1,680                     | 1,740                    | +60  | Medium                |
| MW-CHI    | 1,760                     | 1,820                    | +60  | Low                   |
| NE-NYC    | 1,950                     | 1,980                    | +30  | Medium                |

### Zero Cola — Northeast Retail Shelf & Competitive Intelligence

| Territory | Shelf Share (ours) | Competitor Shelf Share | New Competitor SKUs (last 6mo) | Promo Frequency (wk) | Promo Lift |
|-----------|--------------------|-----------------------|--------------------------------|-----------------------|------------|
| NE-NYC    | 22.5%              | 31.2%                 | 4                              | 1.8                   | +12%       |
| NE-BOS    | 20.1%              | 33.8%                 | 5                              | 1.5                   | +10%       |
| NE-PHL    | 21.8%              | 30.5%                 | 3                              | 1.6                   | +11%       |
| NE-PIT    | 18.5%              | 35.2%                 | 4                              | 1.2                   | +8%        |
| NE-DC     | 24.2%              | 28.8%                 | 2                              | 2.0                   | +14%       |
| NE-BAL    | 19.2%              | 34.1%                 | 4                              | 1.3                   | +9%        |
| NE-HFD    | 17.8%              | 36.5%                 | 5                              | 1.0                   | +7%        |
| NE-PRV    | 16.5%              | 37.8%                 | 5                              | 0.8                   | +6%        |
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


async def send_to_queue(queue_name: str, payload: dict):
    namespace = os.environ["SERVICEBUS_NAMESPACE"]
    async with ServiceBusClient(namespace, credential=async_credential) as client:
        sender = client.get_queue_sender(queue_name=queue_name)
        async with sender:
            msg = ServiceBusMessage(
                body=json.dumps(payload),
                content_type="application/json",
            )
            await sender.send_messages(msg)


# ---------------------------------------------------------------------------
# Service Bus Receiver Loop — Partner Agent
# ---------------------------------------------------------------------------

async def handle_message(body: dict):
    log_lines: list[str] = []

    def log(message: str, cid: str = ""):
        entry = f"[{_timestamp()}] [{cid}] {message}"
        log_lines.append(entry)
        logging.info(entry)

    correlation_id = body.get("correlation_id", "unknown")
    question = body.get("question", "")
    primary_analysis = body.get("primary_analysis", "")

    log("Received request from Service Bus", correlation_id)

    # --- Invoke Partner Agent via MAF ---
    log("Invoking Partner Agent", correlation_id)

    partner_client = OpenAIChatClient(
        azure_endpoint=os.environ["PARTNER_AGENT_OPENAI_ENDPOINT"],
        credential=credential,
        model=os.environ["PARTNER_AGENT_MODEL_DEPLOYMENT"],
    )
    partner_agent = partner_client.as_agent(
        name="PartnerAgent",
        instructions=PARTNER_AGENT_SYSTEM_PROMPT,
    )

    prompt = (
        f"## Original Question\n{question}\n\n"
        f"## Primary Agent Analysis\n{primary_analysis}\n\n"
        "Based on the Primary Agent's territory analysis above, provide your "
        "operational deep-dive focusing on the recommended territories. Analyze "
        "consumption clusters, retail density, distribution coverage, and "
        "demand patterns."
    )

    partner_result = await partner_agent.run(prompt)
    partner_analysis = str(partner_result)

    log("Partner Agent completed", correlation_id)

    # --- Send response to queue ---
    log("Publishing response to Service Bus queue", correlation_id)

    response_payload = {
        "correlation_id": correlation_id,
        "partner_analysis": partner_analysis,
    }
    await send_to_queue("agent-responses", response_payload)

    log("Response published", correlation_id)

    # Upload logs (best-effort)
    try:
        await upload_log(correlation_id, "partner-agent", log_lines)
    except Exception as e:
        logging.warning(f"Failed to upload partner-agent logs: {e}")


async def receiver_loop():
    namespace = os.environ["SERVICEBUS_NAMESPACE"]
    logging.info("Partner Agent started — waiting for messages on Service Bus")

    async with ServiceBusClient(namespace, credential=async_credential) as sb_client:
        receiver = sb_client.get_subscription_receiver(
            topic_name="agent-requests",
            subscription_name="partner-agent-sub",
        )
        async with receiver:
            while True:
                msgs = await receiver.receive_messages(
                    max_wait_time=30,
                    max_message_count=1,
                )
                for msg in msgs:
                    try:
                        body = json.loads(str(msg))
                    except (json.JSONDecodeError, TypeError):
                        raw = msg.body
                        if isinstance(raw, bytes):
                            body = json.loads(raw.decode("utf-8"))
                        else:
                            body = json.loads(b"".join(raw).decode("utf-8"))

                    try:
                        await handle_message(body)
                        await receiver.complete_message(msg)
                    except Exception:
                        logging.exception("Error processing message")
                        await receiver.abandon_message(msg)


if __name__ == "__main__":
    asyncio.run(receiver_loop())
