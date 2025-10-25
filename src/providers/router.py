from .openai import OpenAILike
from .gemini import GeminiClient

def build_llm(provider: str, model: str, api_key: str, base_url: str | None):
    p = provider.lower()
    if p in {"groq", "openai"}:
        return OpenAILike(model=model, api_key=api_key, base_url=base_url)
    if p == "gemini":
        return GeminiClient(model=model, api_key=api_key)
    raise ValueError(f"Unknown provider: {provider}")
