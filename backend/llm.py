"""LangChain model factories, configured from config.toml.

Nodes call get_llm() / get_embeddings() instead of building clients themselves,
so the model and its settings are changed in one place (the Admin page).
Clients are cached per distinct configuration, so a config change (hot reload)
automatically produces a new client on the next call.

Reasoning models (e.g. gpt-6-luna) reject a custom temperature and take
`reasoning_effort` instead; standard models take `temperature`.
"""
from functools import lru_cache

from config import get_settings


@lru_cache(maxsize=8)
def _chat_openai(model: str, kind: str, effort: str, temperature: float, max_tokens: int,
                 timeout_s: int, max_retries: int, api_key: str):
    from langchain_openai import ChatOpenAI

    kwargs = dict(model=model, max_tokens=max_tokens, timeout=timeout_s, max_retries=max_retries,
                  api_key=api_key or None)
    if kind == "reasoning":
        kwargs["reasoning_effort"] = effort
    else:
        kwargs["temperature"] = temperature
    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=4)
def _openai_embeddings(model: str, dimension: int, batch_size: int, api_key: str):
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=model, dimensions=dimension, chunk_size=batch_size, api_key=api_key or None)


def get_llm():
    s = get_settings()
    c = s.llm
    if c.provider != "openai":
        raise ValueError(f"Unsupported LLM provider: {c.provider}")
    return _chat_openai(c.model, c.model_kind, c.reasoning_effort, c.temperature, c.max_tokens,
                        c.timeout_s, c.max_retries, s.openai_api_key)


def get_embeddings():
    s = get_settings()
    c = s.embeddings
    if c.provider != "openai":
        raise ValueError(f"Unsupported embeddings provider: {c.provider}")
    return _openai_embeddings(c.model, c.dimension, c.batch_size, s.openai_api_key)
