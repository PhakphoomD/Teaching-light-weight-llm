from typing import List, Dict, Any
Message = Dict[str, str]  # {"role":"system|user|assistant","content":"..."}

class LLMClient:
    def chat(self, messages: List[Message], temperature: float, max_tokens: int, top_p: float, timeout_s: int) -> dict:
        raise NotImplementedError()
    @property
    def name(self) -> str: raise NotImplementedError()
