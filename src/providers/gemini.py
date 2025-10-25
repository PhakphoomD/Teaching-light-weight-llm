import google.generativeai as genai
from .base import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def chat(self, messages, temperature, max_tokens, top_p, timeout_s):
        prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        resp = self.model.generate_content(
            prompt, generation_config={"temperature": temperature, "top_p": top_p, "max_output_tokens": max_tokens}
        )
        return {"text": resp.text or "", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    @property
    def name(self) -> str: return str(self.model)
