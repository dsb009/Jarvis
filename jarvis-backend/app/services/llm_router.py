"""LLM Router - Routes tasks to appropriate LLM based on complexity."""
import google.generativeai as genai
from openai import AsyncOpenAI
from typing import Optional, Type
from pydantic import BaseModel
from app.core.config import settings


class LLMRouter:
    """
    Routes LLM requests to the appropriate model:
    - Simple tasks: Gemini 1.5 Flash ($0.075/1M tokens)
    - Complex tasks: GPT-4.1 nano ($0.10/1M tokens)
    """

    COMPLEX_KEYWORDS = [
        "plan", "analyze", "reason", "synthesize", "design",
        "strategy", "compare", "evaluate", "optimize", "debug",
        "orchestrate", "coordinate", "multi-step", "complex",
    ]

    SIMPLE_KEYWORDS = [
        "classify", "extract", "format", "summarize", "validate",
        "parse", "convert", "simple", "quick", "basic", "list",
    ]

    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini = genai.GenerativeModel("gemini-1.5-flash")

        if settings.OPENAI_API_KEY:
            self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def route(self, task_description: str) -> str:
        """
        Determine which LLM to use based on task complexity.

        Returns:
            "gemini" for simple tasks
            "gpt-4.1-nano" for complex tasks
        """
        task_lower = task_description.lower()

        # Check for complex indicators
        if any(keyword in task_lower for keyword in self.COMPLEX_KEYWORDS):
            return "gpt-4.1-nano"

        # Check for simple indicators
        if any(keyword in task_lower for keyword in self.SIMPLE_KEYWORDS):
            return "gemini"

        # Default: Use Gemini for speed/cost efficiency
        # Can be overridden by explicit agent type
        return "gemini"

    async def call(
        self,
        task_description: str,
        system: str,
        user: str,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str | BaseModel:
        """
        Call the appropriate LLM based on task complexity.
        """
        model = self.route(task_description)

        if model == "gpt-4.1-nano":
            return await self._call_gpt(
                system=system,
                user=user,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            return await self._call_gemini(
                system=system,
                user=user,
                response_model=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    async def _call_gpt(
        self,
        system: str,
        user: str,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str | BaseModel:
        """Call GPT-4.1 nano via OpenAI."""
        if not self.openai:
            raise ValueError("OpenAI API key not configured")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        kwargs = {
            "model": "gpt-4.1-nano",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_model:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema()
                }
            }

        response = await self.openai.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        if response_model:
            return response_model.model_validate_json(content)
        return content

    async def _call_gemini(
        self,
        system: str,
        user: str,
        response_model: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str | BaseModel:
        """Call Gemini 1.5 Flash via Google Generative AI."""
        if not self.gemini:
            raise ValueError("Gemini API key not configured")

        prompt = f"{system}\n\nUser: {user}"

        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        response = await self.gemini.generate_content_async(
            prompt,
            generation_config=generation_config,
        )

        content = response.text

        if response_model:
            return response_model.model_validate_json(content)
        return content


# Singleton instance
llm_router = LLMRouter()