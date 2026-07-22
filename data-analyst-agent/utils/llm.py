"""
llm.py

Handles all communication with Ollama (qwen2.5:3b).
- Checks if Ollama is reachable
- Pulls the model if not already available
- Sends prompts and returns responses

OLLAMA_BASE_URL / OLLAMA_MODEL can be overridden for AWS (e.g. EC2 Ollama).
"""

import os

import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")


def is_ollama_running() -> bool:
    """Ping Ollama to see if the service is up."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def pull_model() -> bool:
    """
    Pull the qwen2.5:3b model (non-blocking progress is printed server-side).
    Returns True once the model is pulled successfully.
    """
    try:
        payload = {"name": MODEL_NAME, "stream": False}
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json=payload,
            timeout=300,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _build_payload(system_prompt: str, user_prompt: str) -> dict:
    """Construct the JSON payload for Ollama's chat API."""
    return {
        "model": MODEL_NAME,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def generate_response(system_prompt: str, user_prompt: str, timeout: int = 120) -> str:
    """
    Send a prompt to Ollama and return the model's text response.
    Never raises – returns a readable warning on failure.
    """
    if not is_ollama_running():
        return (
            "**Ollama is not running.**\n\n"
            "Please start it with:\n"
            "```bash\n"
            "ollama serve\n"
            "```\n"
            "Or open the Ollama desktop application."
        )

    payload = _build_payload(system_prompt, user_prompt)

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "No response from model.")
    except requests.exceptions.Timeout:
        return "Request timed out. The model might still be loading – try again."
    except requests.RequestException as exc:
        return f"Error communicating with Ollama: {exc}"
