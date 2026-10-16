"""
LLM Provider module for LinkedIn Daily Bot.
Provides an abstract base interface with Anthropic Claude as default,
and swappable support for OpenAI and compatible APIs.
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional
import anthropic
import requests

from .config import Config

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM text generation."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """Generate response text given system and user prompts."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API client."""

    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022"):
        if not api_key:
            raise ValueError("Anthropic API key is required but missing.")
        self.api_key = api_key
        self.model_name = model_name
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        logger.info(f"Generating post with Anthropic model: {self.model_name}")
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=400,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        # Extract text from content blocks
        full_text = ""
        for block in message.content:
            if hasattr(block, "text"):
                full_text += block.text
        return full_text.strip()


class OpenAIProvider(LLMProvider):
    """OpenAI API client (uses direct HTTP to avoid heavy extra dependencies)."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        if not api_key:
            raise ValueError("OpenAI API key is required but missing.")
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        logger.info(f"Generating post with OpenAI model: {self.model_name}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 400
        }
        res = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if res.status_code != 200:
            raise RuntimeError(f"OpenAI API call failed ({res.status_code}): {res.text}")
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()


class GeminiProvider(LLMProvider):
    """Google Gemini API client using the official google-genai SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("Gemini API key is required but missing (set GEMINI_API_KEY in .env).")
        # Accept any valid key format (including AQ. and AIzaSy) without alteration or prefix checks
        self.api_key = api_key.strip()
        self.model_name = model_name
        from google import genai
        from google.genai import types
        # Native Gemini endpoint https://generativelanguage.googleapis.com/v1beta/ with x-goog-api-key header
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                headers={"x-goog-api-key": self.api_key}
            )
        )

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        logger.info(f"Generating post with Google Gemini model: {self.model_name}")
        from google.genai import types

        # List of candidate models to try in order
        candidates = [self.model_name]
        for alt in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
            if alt not in candidates:
                candidates.append(alt)

        last_err = None
        for model_to_use in candidates:
            try:
                if model_to_use != self.model_name:
                    logger.info(f"Retrying with alternative model: {model_to_use}")
                response = self.client.models.generate_content(
                    model=model_to_use,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        max_output_tokens=2048,
                    ),
                )
                return (response.text or "").strip()
            except Exception as e:
                last_err = e
                err_str = str(e)
                # Retry on 404 (model retired for new users) or 503 (temporary high demand spike)
                if any(k in err_str for k in ("no longer available", "404", "503", "UNAVAILABLE", "not found")):
                    logger.warning(f"Model '{model_to_use}' failed ({err_str[:90]}...). Trying next candidate...")
                    continue
                raise e

        raise last_err


class MockLLMProvider(LLMProvider):
    """Mock provider useful for offline testing and development."""

    def __init__(self, predefined_response: Optional[str] = None):
        self.predefined_response = predefined_response

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        if self.predefined_response:
            return self.predefined_response
        return (
            "OpenAI announced yesterday that GPT-4o voice mode rolled out to all users.\n"
            "Sub-300ms latency finally makes voice interaction feel natural instead of clunky.\n"
            "Real-time voice might replace typing faster than most people expect.\n"
            "Have you tried the new voice latency yet?\n\n"
            "#ArtificialIntelligence #OpenAI #TechNews #VoiceAI\n\n"
            "https://openai.com/blog"
        )


def get_llm_provider(config: Config) -> LLMProvider:
    """Factory to instantiate the configured LLM provider."""
    provider_name = config.llm_provider.lower()
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=config.gemini_api_key,
            model_name=config.gemini_model
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model_name=config.anthropic_model
        )
    elif provider_name == "openai":
        return OpenAIProvider(
            api_key=config.openai_api_key,
            model_name=config.openai_model
        )
    elif provider_name == "mock":
        return MockLLMProvider()
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider_name}'. Supported: 'gemini', 'anthropic', 'openai', 'mock'"
        )
