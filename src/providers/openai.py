# from openai import OpenAI
# from .base import LLMClient

# class OpenAILike(LLMClient):
#     def __init__(self, model: str, api_key: str, base_url: str | None = None):
#         self.model = model
#         self.client = OpenAI(api_key=api_key, base_url=base_url)

#     def chat(self, messages, temperature, max_tokens, top_p, timeout_s):
#         r = self.client.chat.completions.create(
#             model=self.model, messages=messages, temperature=temperature,
#             max_tokens=max_tokens, top_p=top_p, timeout=timeout_s
#         )
#         msg = r.choices[0].message.content or ""
#         usage = r.usage or None
#         return {"text": msg,
#                 "usage": {"prompt_tokens": getattr(usage, "prompt_tokens", 0),
#                           "completion_tokens": getattr(usage, "completion_tokens", 0),
#                           "total_tokens": getattr(usage, "total_tokens", 0)}}
#     @property
#     def name(self) -> str: return self.model
