from __future__ import annotations
import os, yaml
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv


class ProviderSpec(BaseModel):
    provider: str = Field(..., pattern="^(openai|groq|gemini)$")
    model: str
    timeout_s: int = 20

class TeacherCfg(BaseModel):
    providers: list[ProviderSpec]
    temperature: float = 0.2
    max_tokens: int = 512
    top_p: float = 0.9
    rate_limit_rps: float = 2.0

class StudentCfg(BaseModel):
    mode: str = Field("local", pattern="^(local|api)$")
    model: str
    device: str = "auto"
    max_new_tokens: int = 128
    temperature: float = 0.6
    top_p: float = 0.9
    providers: list[ProviderSpec] | None = None  # used when mode=api

class MemoryCfg(BaseModel):
    encoder: str
    dim: int
    index_path: str
    store_path: str
    k: int = 5
    retrieval: dict = Field(default_factory=lambda: {
        "k_task": 2,
        "k_similar": 2,
        "tfidf": {"min_cosine": 0.30},
        "ngram": {"jaccard": 0.12}
    })
    reflection: dict = Field(default_factory=lambda: {
        "temperature_next": 0.25,
        "max_tokens_next": 160
    })

class EvalCfg(BaseModel):
    test_path: str
    metrics: list[str]
    reports_dir: str

class CostCfg(BaseModel):
    currency: str = "AUD"
    prices_per_1k_tokens: dict = {}

class RootCfg(BaseModel):
    teacher: TeacherCfg
    student: StudentCfg
    memory: MemoryCfg
    evaluation: EvalCfg
    costing: CostCfg

class Secrets(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None

def _secrets(provider: str) -> Secrets:
    p = provider.lower()
    if p == "groq":
        return Secrets(provider=p, api_key=os.getenv("GROQ_API_KEY"),
                       base_url=os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1")
    if p == "openai":
        return Secrets(provider=p, api_key=os.getenv("OPENAI_API_KEY"),
                       base_url=os.getenv("OPENAI_BASE_URL") or None)
    if p == "gemini":
        return Secrets(provider=p, api_key=os.getenv("GOOGLE_API_KEY"))
    return Secrets(provider=p)

def load_config(path: str = "config/config.yaml") -> tuple[RootCfg, Secrets]:
    load_dotenv(override=False)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    cfg = RootCfg(**raw)

    # default secret uses FIRST teacher provider as the bootstrap
    bootstrap = cfg.teacher.providers[0].provider
    sec = _secrets(bootstrap)
    if not sec.api_key and bootstrap in {"groq","openai","gemini"}:
        raise RuntimeError(f"Missing API key for provider: {bootstrap}")
    return cfg, sec
