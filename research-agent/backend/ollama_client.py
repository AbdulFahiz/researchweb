import httpx
import json
from typing import AsyncGenerator, List, Dict, Any

OLLAMA_BASE_URL = "http://localhost:11434"

async def chat_stream(
    model: str,
    messages: List[Dict[str, str]],
    system: str = ""
) -> AsyncGenerator[str, None]:
    """
    Streams responses from the Ollama API.
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages if system else messages,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    yield f"Error: Failed to connect to Ollama. Status: {response.status_code}. Response: {error_content.decode()}"
                    return

                async for chunk in response.aiter_bytes():
                    if chunk:
                        try:
                            # Ollama streams JSON objects separated by newlines
                            lines = chunk.decode('utf-8').split('\n')
                            for line in lines:
                                if line:
                                    data = json.loads(line)
                                    if data.get("done") is False:
                                        yield data["message"]["content"]
                        except json.JSONDecodeError:
                            # In case of partial JSON chunks
                            pass
    except httpx.ConnectError as e:
        yield f"Error: Connection to Ollama failed. Is Ollama running at {OLLAMA_BASE_URL}? Details: {e}"
    except Exception as e:
        yield f"Error: An unexpected error occurred. {e}"


async def chat_complete(
    model: str,
    messages: List[Dict[str, str]],
    system: str = ""
) -> str:
    """
    Gets a complete response from the Ollama API.
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages if system else messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            return response_json["message"]["content"]
    except httpx.ConnectError as e:
        return f"Error: Connection to Ollama failed. Is Ollama running at {OLLAMA_BASE_URL}? Details: {e}"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP error occurred: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error: An unexpected error occurred. {e}"

async def get_available_models() -> List[str]:
    """
    Fetches the list of available models from Ollama.
    """
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            models_data = response.json()
            return [model["name"] for model in models_data.get("models", [])]
    except (httpx.ConnectError, httpx.HTTPStatusError, KeyError):
        return ["llama3.2", "mistral", "deepseek-r1"] # Fallback list
