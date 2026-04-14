# Author: Vicente Maciel Junior (vicentem@microsoft.com)
# Cloud & AI Solutions Architect

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

ORCHESTRATOR_URL = "http://localhost:7071/api/ask"
REQUEST_TIMEOUT = 300  # seconds — accounts for both agents processing


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def main():
    print(f"[{_ts()}] Starting orchestrator client...")
    print(f"[{_ts()}] Orchestrator endpoint: {ORCHESTRATOR_URL}")
    print()

    while True:
        correlation_id = str(uuid.uuid4())[:8]
        print(f"[{_ts()}] Correlation ID: {correlation_id}")
        print()

        try:
            question = input(f"[{_ts()}] > Enter your question (or 'quit' to exit): ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        question = question.strip()
        if not question or question.lower() in ("quit", "exit", "q"):
            print("Exiting.")
            break

        print(f"[{_ts()}] Sending question to orchestrator...")
        print(f"[{_ts()}] Waiting for response (this may take a minute)...")
        print()

        payload = {
            "question": question,
            "correlation_id": correlation_id,
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                response = client.post(
                    ORCHESTRATOR_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            if response.status_code != 200:
                print(f"[{_ts()}] Error: HTTP {response.status_code}")
                print(response.text)
                print()
                continue

            data = response.json()

            print(f"[{_ts()}] Response received from orchestrator:")
            print()
            print("=" * 72)
            print("  PRIMARY AGENT ANALYSIS")
            print("=" * 72)
            print()
            print(data.get("primary_agent_analysis", "(no response)"))
            print()
            print("=" * 72)
            print("  PARTNER AGENT ANALYSIS")
            print("=" * 72)
            print()
            print(data.get("partner_agent_analysis", "(no response)"))
            print()
            print("=" * 72)
            print(f"[{_ts()}] Done. (correlation_id: {correlation_id})")
            print()

        except httpx.ConnectError:
            print(
                f"[{_ts()}] Connection error: Could not reach the orchestrator at "
                f"{ORCHESTRATOR_URL}"
            )
            print(
                f"[{_ts()}] Make sure the orchestrator function is running "
                f"(func start --port 7071)."
            )
            print()
        except httpx.ReadTimeout:
            print(f"[{_ts()}] Timeout: The orchestrator did not respond within {REQUEST_TIMEOUT}s.")
            print()
        except Exception as e:
            print(f"[{_ts()}] Unexpected error: {e}")
            print()


if __name__ == "__main__":
    main()
