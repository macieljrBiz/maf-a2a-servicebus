# Demo Setup Guide

> **Author:** Vicente Maciel Junior — vicentem@microsoft.com — Cloud & AI Solutions Architect

This guide covers everything you need to deploy on Azure and configure locally to run the multi-agent orchestration demo.

## Prerequisites

- **Python 3.12** installed (Microsoft Agent Framework 1.0.1 is not compatible with Python 3.14; versions 3.10–3.13 are supported). If you use `uv`, it can install Python for you — see Step 1 below.
- **uv** installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/)).
- **Azure CLI** installed and authenticated (`az login`).
- An active **Azure subscription**.

## Azure Resources to Deploy

You need to create the following resources in your Azure subscription. We use **two resource groups** to simulate the cross-organization boundary.

### Resource Group 1: Orchestrator (Main Organization)

```bash
az group create --name rg-a2a-demo-orchestrator --location eastus
```

#### 1. Azure Service Bus Namespace (Standard tier)

Standard tier is required to support topics and subscriptions.

```bash
az servicebus namespace create \
  --name sbns-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator \
  --sku Standard \
  --location eastus
```

Create the **topic** for sending requests to the Partner Agent:

```bash
az servicebus topic create \
  --name agent-requests \
  --namespace-name sbns-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator
```

Create a **subscription** on the topic for the Partner Agent to consume:

```bash
az servicebus topic subscription create \
  --name partner-agent-sub \
  --topic-name agent-requests \
  --namespace-name sbns-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator
```

Create the **response queue** for the Partner Agent to send results back:

```bash
az servicebus queue create \
  --name agent-responses \
  --namespace-name sbns-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator
```

Assign **Azure Service Bus Data Owner** role to your user (required for `DefaultAzureCredential` access):

```bash
az role assignment create \
  --role "Azure Service Bus Data Owner" \
  --assignee $(az ad signed-in-user show --query id --output tsv) \
  --scope $(az servicebus namespace show --name sbns-demo-orchestrator --resource-group rg-a2a-demo-orchestrator --query id --output tsv)
```

#### 2. Azure Storage Account (for log files)

```bash
az storage account create \
  --name stdemoorchestrator \
  --resource-group rg-a2a-demo-orchestrator \
  --sku Standard_LRS \
  --location eastus
```

Assign **Storage Blob Data Contributor** role to your user (required for `DefaultAzureCredential` access):

```bash
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee $(az ad signed-in-user show --query id --output tsv) \
  --scope $(az storage account show --name stdemoorchestrator --resource-group rg-a2a-demo-orchestrator --query id --output tsv)
```

Create the **blob container** for log files (using identity-based auth):

```bash
az storage container create \
  --name agent-logs \
  --account-name stdemoorchestrator \
  --auth-mode login
```

### Resource Group 2: Partner Agent (Simulated Partner Infrastructure)

```bash
az group create --name rg-a2a-demo-partner --location eastus
```

> **Note**: In production, this resource group would be in a separate subscription/tenant owned by the partner organization. For the demo, we use a separate resource group in the same subscription to simulate the boundary.

No additional resources are needed in this group for local execution — the Partner Agent Function App only needs access to the shared Service Bus and its own Azure OpenAI deployment.

### Azure OpenAI Deployments

You need **two separate model deployments** — one for each agent. These can be in the same or different Azure OpenAI resources. You can use existing Azure OpenAI resources or create new ones as described below.

#### (Optional) Create Azure OpenAI Resources

If you don't have existing Azure OpenAI resources, create one in each resource group. This reinforces the cross-organization boundary — each organization owns its own AI resource.

**Orchestrator resource** (for the Primary Agent):

```bash
az cognitiveservices account create \
  --name aoai-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator \
  --kind OpenAI \
  --sku S0 \
  --location eastus \
  --custom-domain aoai-demo-orchestrator
```

**Partner resource** (for the Partner Agent):

```bash
az cognitiveservices account create \
  --name aoai-demo-partner \
  --resource-group rg-a2a-demo-partner \
  --kind OpenAI \
  --sku S0 \
  --location eastus \
  --custom-domain aoai-demo-partner
```

> **Note**: The `--custom-domain` parameter is required for identity-based (Entra ID) authentication. Without it, the resource only supports key-based auth.

#### Model Selection

The demo requires a chat completion model with good instruction-following and reasoning capabilities. Both agents can use the same or different models. The table below lists recommended models:

| Model | Version | Context Window | Suggested Use | Rationale |
|---|---|---|---|---|
| `gpt-4o` | `2024-11-20` | 128K | **Recommended for both agents** | Best balance of quality, speed, and cost. Strong instruction-following for complex analytical prompts. |
| `gpt-4o-mini` | `2024-07-18` | 128K | Cost-sensitive demos | ~10x cheaper than gpt-4o. Good for quick iterations and testing, but may produce shallower analysis. |
| `gpt-4.1` | `2025-04-14` | 1M | Deep analysis tasks | Latest generation model with massive context window. Best reasoning quality, but higher latency and cost. |
| `gpt-4.1-mini` | `2025-04-14` | 1M | Balanced alternative | Smaller variant of gpt-4.1 with large context. Good quality-to-cost ratio for analytical workloads. |
| `gpt-4.1-nano` | `2025-04-14` | 1M | Lightweight/budget demos | Fastest and cheapest gpt-4.1 variant. Suitable for demos where response quality is less critical. |

> **Tip**: For the demo, `gpt-4o` (`2024-11-20`) is the recommended choice. It provides strong analytical output without excessive latency. You can list all available models on your resource with:
> ```bash
> az cognitiveservices account list-models \
>   --name {openai-resource-name} \
>   --resource-group {resource-group} \
>   --query "[?name != null].{name:name, version:version, lifecycleStatus:lifecycleStatus}" \
>   --output table
> ```

#### Deploy the Model

Once you've selected a model, deploy it on each Azure OpenAI resource. Replace `{model-name}` and `{model-version}` with your selection from the table above.

**Deploy on the Orchestrator resource**:

```bash
az cognitiveservices account deployment create \
  --name aoai-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator \
  --deployment-name primary-agent \
  --model-name {model-name} \
  --model-version {model-version} \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

**Deploy on the Partner resource**:

```bash
az cognitiveservices account deployment create \
  --name aoai-demo-partner \
  --resource-group rg-a2a-demo-partner \
  --deployment-name partner-agent \
  --model-name {model-name} \
  --model-version {model-version} \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

> **Note**: `--sku-capacity` sets the tokens-per-minute (TPM) quota in thousands. `10` = 10K TPM, which is sufficient for demo purposes. Increase for production workloads.

For example, to deploy `gpt-4o` version `2024-11-20` on both resources:

```bash
# Primary Agent
az cognitiveservices account deployment create \
  --name aoai-demo-orchestrator \
  --resource-group rg-a2a-demo-orchestrator \
  --deployment-name primary-agent \
  --model-name gpt-4o \
  --model-version 2024-11-20 \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

# Partner Agent
az cognitiveservices account deployment create \
  --name aoai-demo-partner \
  --resource-group rg-a2a-demo-partner \
  --deployment-name partner-agent \
  --model-name gpt-4o \
  --model-version 2024-11-20 \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

#### Assign RBAC for Azure OpenAI

Assign the **Cognitive Services OpenAI User** role on each Azure OpenAI resource to your user:

```bash
# Orchestrator resource
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $(az ad signed-in-user show --query id --output tsv) \
  --scope $(az cognitiveservices account show --name aoai-demo-orchestrator --resource-group rg-a2a-demo-orchestrator --query id --output tsv)

# Partner resource
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $(az ad signed-in-user show --query id --output tsv) \
  --scope $(az cognitiveservices account show --name aoai-demo-partner --resource-group rg-a2a-demo-partner --query id --output tsv)
```

> **Note**: If you are using existing Azure OpenAI resources instead of the ones created above, replace the resource names and resource groups in the `--scope` accordingly.

## Environment Configuration

All configuration is managed via a single `.env` file in the `sample/` directory.

### Create the `.env` File

Create `sample/.env` with the following content, replacing the placeholder values with your actual values:

```env
# Azure Service Bus (identity-based auth via DefaultAzureCredential)
SERVICEBUS_NAMESPACE=sbns-demo-orchestrator.servicebus.windows.net

# Azure Storage Account (identity-based auth via DefaultAzureCredential)
STORAGE_ACCOUNT_URL=https://stdemoorchestrator.blob.core.windows.net/

# Azure OpenAI — Primary Agent (identity-based auth via DefaultAzureCredential)
PRIMARY_AGENT_OPENAI_ENDPOINT=https://aoai-demo-orchestrator.openai.azure.com/
PRIMARY_AGENT_MODEL_DEPLOYMENT=primary-agent

# Azure OpenAI — Partner Agent (identity-based auth via DefaultAzureCredential)
PARTNER_AGENT_OPENAI_ENDPOINT=https://aoai-demo-partner.openai.azure.com/
PARTNER_AGENT_MODEL_DEPLOYMENT=partner-agent
```

> **Note**: No secrets are stored in the `.env` file. All authentication uses `DefaultAzureCredential`, which locally falls back to your `az login` credentials. The `.env` file should still be listed in `.gitignore` as a best practice.

## Running the Demo

You will need **three terminal windows** (one for each component). All commands below assume you start from the repository root.

### Step 1: Authenticate with Azure

Before starting the applications, make sure you have an active Azure CLI session:

```bash
az login
```

`DefaultAzureCredential` falls back to `AzureCliCredential` for local execution, so all three applications require a valid `az login` session to access Service Bus, Storage, and Azure OpenAI.

### Step 2: (Optional) Install Python 3.12 via uv

If you don't have Python 3.12 on your system, `uv` can install it for you:

```bash
uv python install 3.12
```

This downloads and manages a local Python 3.12 distribution — no system-wide install required.

### Step 3: Start the Partner Agent (Terminal 1)

Open a terminal and run:

```bash
cd sample/app-partner-agent
uv sync --python 3.12
uv run python main.py
```

**Wait until you see**: `Partner Agent started — waiting for messages on Service Bus`

This confirms the agent connected to the Service Bus subscription and is ready to process requests.

### Step 4: Start the Orchestrator (Terminal 2)

Open a **second** terminal and run:

```bash
cd sample/app-orchestrator
uv sync --python 3.12
uv run python main.py
```

**Wait until you see**: `Uvicorn running on http://0.0.0.0:7071`

The orchestrator HTTP server is now accepting requests.

### Step 5: Run the Client (Terminal 3)

Open a **third** terminal and run:

```bash
cd sample/client
uv sync --python 3.12
uv run python main.py
```

The client opens an interactive prompt. Type a question and press Enter. For example:

> *Analyze the opportunity for launching a 350ml Classic Cola can in the Southeast region. Which territories show the highest potential based on current brand performance?*

The response may take 30–60 seconds as both agents process the request.

### What Happens Under the Hood

1. The **Client** sends your question via HTTP POST to `http://localhost:7071/api/ask`.
2. The **Orchestrator** invokes the **Primary Agent** (territory analysis via Azure OpenAI), then publishes the result to Service Bus topic `agent-requests`.
3. The **Partner Agent** picks up the message from its subscription, runs an operational deep-dive analysis (via its own Azure OpenAI deployment), and publishes the response to queue `agent-responses`.
4. The **Orchestrator** receives the Partner Agent response from the queue, combines both analyses, and returns the consolidated result to the Client.
5. The **Client** displays the Primary Agent analysis and the Partner Agent analysis side by side.

### Suggested Test Questions

| # | Question |
|---|---|
| 1 | *Analyze the opportunity for launching a 350ml Classic Cola can in the Southeast region. Which territories show the highest potential based on current brand performance?* |
| 2 | *Zero Cola has been declining in the Northeast region over the last two quarters. What's driving the drop, and which territories need immediate attention?* |
| 3 | *We're rationalizing the product portfolio in the Midwest region. Which low-performing SKUs should we consider discontinuing, and what's the risk of losing shelf space?* |
| 4 | *Summer peak is approaching. Based on last year's performance, which territories in the South region need increased distribution capacity for the Classic Cola 2L package?* |

### Stopping the Demo

Press `Ctrl+C` in each terminal to stop the Partner Agent and Orchestrator.

## Verifying the Logs

After running the demo, check the log files in the Storage Account:

```bash
az storage blob list \
  --container-name agent-logs \
  --account-name stdemoorchestrator \
  --auth-mode login \
  --output table
```

Download a specific log:

```bash
az storage blob download \
  --container-name agent-logs \
  --account-name stdemoorchestrator \
  --name "logs/{correlation-id}-orchestrator.log" \
  --file orchestrator.log \
  --auth-mode login
```

## Cleanup

To remove all Azure resources created for this demo:

```bash
az group delete --name rg-a2a-demo-orchestrator --yes --no-wait
az group delete --name rg-a2a-demo-partner --yes --no-wait
```
