"""LLM client using Ollama."""
import httpx
from typing import Optional, Type
from pydantic import BaseModel
from app.core.config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 120.0

    async def call(
        self,
        system: str,
        user: str,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str | BaseModel:
        prompt = f"{system}\n\nUser: {user}\nAssistant:"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "options": {"num_predict": max_tokens},
                    "stream": False,
                },
            )
            response.raise_for_status()
            content = response.json()["response"]

        if response_model:
            return response_model.model_validate_json(content)
        return content

    async def chat(
        self,
        messages: list[dict],
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str | BaseModel:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "options": {"num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]

        if response_model:
            return response_model.model_validate_json(content)
        return content


llm_client = OllamaClient()