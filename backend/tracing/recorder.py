"""TraceRecorder: our own tracing, built on LangChain callbacks.

How it works (the same mechanism hosted tracers use):
- We pass one handler in the run config: graph.invoke(state, config={"callbacks": [recorder]}).
- LangChain propagates the config to *every* nested Runnable: the graph, each
  node, each prompt/parser/model inside a node. Each one fires start/end/error
  events carrying its own `run_id` and its parent's `parent_run_id`.
- Recording each event as a "span" with (span_id=run_id, parent=parent_run_id)
  rebuilds the full call tree: graph -> node -> chain -> LLM call.

Spans are written to SQLite (trace_spans) as they start and finish, so a
running run can be inspected live.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from pydantic import BaseModel

from db.sqlite import insert_span, update_span

log = logging.getLogger(__name__)

HIDDEN_TAG = "langsmith:hidden"  # LangGraph marks its internal plumbing runnables with this tag


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return str(obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, BaseMessage):
        d = {"role": obj.type, "content": _jsonable(obj.content, depth + 1)}
        if getattr(obj, "tool_calls", None):
            d["tool_calls"] = _jsonable(obj.tool_calls, depth + 1)
        return d
    if isinstance(obj, Document):
        return {"page_content": obj.page_content, "metadata": _jsonable(obj.metadata, depth + 1)}
    if isinstance(obj, BaseModel):
        return _jsonable(obj.model_dump(), depth + 1)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v, depth + 1) for v in obj]
    if isinstance(obj, UUID):
        return str(obj)
    return str(obj)


class TraceRecorder(BaseCallbackHandler):
    """Records every chain / node / LLM / tool / retriever call of one app run."""

    raise_error = False  # tracing must never break a run

    def __init__(self, app_run_id: int, max_payload_chars: int = 6000):
        self.app_run_id = app_run_id
        self.max_chars = max_payload_chars
        self._lock = threading.Lock()
        self._t0: dict[str, float] = {}
        self._hidden_parent: dict[str, str | None] = {}  # hidden span -> its visible parent
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.reasoning_tokens = 0
        self.llm_calls = 0

    # ------------------------------------------------------------- helpers
    def _dump(self, obj: Any) -> str:
        s = json.dumps(_jsonable(obj), ensure_ascii=False, default=str)
        if len(s) > self.max_chars:
            s = json.dumps({"_truncated": True, "chars": len(s), "preview": s[: self.max_chars]})
        return s

    def _visible_parent(self, parent: UUID | None) -> str | None:
        p = str(parent) if parent else None
        with self._lock:
            while p in self._hidden_parent:  # skip over hidden plumbing spans
                p = self._hidden_parent[p]
        return p

    def _start(self, run_id: UUID, parent_run_id: UUID | None, name: str, span_type: str,
               inputs: Any, tags: list[str] | None, metadata: dict | None, **extra: Any) -> None:
        sid = str(run_id)
        parent = self._visible_parent(parent_run_id)
        if tags and HIDDEN_TAG in tags:
            with self._lock:
                self._hidden_parent[sid] = parent
            return
        with self._lock:
            self._t0[sid] = time.perf_counter()
        meta = {k: v for k, v in (metadata or {}).items() if not k.startswith("checkpoint")}
        if tags:
            meta["tags"] = tags
        meta.update(extra.pop("extra_meta", {}))
        try:
            insert_span({
                "span_id": sid,
                "run_id": self.app_run_id,
                "parent_span_id": parent,
                "name": name,
                "span_type": span_type,
                "status": "running",
                "started_at": _now_iso(),
                "inputs_json": self._dump(inputs),
                "metadata_json": self._dump(meta),
                **extra,
            })
        except Exception:  # never let tracing break the run
            log.exception("trace: failed to insert span %s", name)

    def _end(self, run_id: UUID, outputs: Any = None, error: BaseException | None = None, **extra: Any) -> None:
        sid = str(run_id)
        with self._lock:
            if sid in self._hidden_parent:
                return
            t0 = self._t0.pop(sid, None)
        fields: dict[str, Any] = {
            "status": "error" if error else "ok",
            "ended_at": _now_iso(),
            "duration_ms": int((time.perf_counter() - t0) * 1000) if t0 else None,
            **extra,
        }
        if outputs is not None:
            fields["outputs_json"] = self._dump(outputs)
        if error is not None:
            fields["error"] = f"{type(error).__name__}: {error}"[:4000]
        try:
            update_span(sid, fields)
        except Exception:
            log.exception("trace: failed to update span %s", sid)

    @staticmethod
    def _name(serialized: dict | None, kwargs: dict, default: str) -> str:
        if kwargs.get("name"):
            return kwargs["name"]
        if serialized:
            if serialized.get("name"):
                return serialized["name"]
            if serialized.get("id"):
                return serialized["id"][-1]
        return default

    # ------------------------------------------------------------- chains / graph / nodes
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        name = self._name(serialized, kwargs, "chain")
        if parent_run_id is None:
            span_type = "graph"
        elif metadata and metadata.get("langgraph_node") == name:
            span_type = "node"
        else:
            span_type = "chain"
        self._start(run_id, parent_run_id, name, span_type, inputs, tags, metadata)

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._end(run_id, outputs)

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error=error)

    # ------------------------------------------------------------- LLMs
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None,
                            metadata=None, **kwargs):
        params = kwargs.get("invocation_params") or {}
        model = params.get("model") or params.get("model_name") or (metadata or {}).get("ls_model_name")
        safe_params = {k: v for k, v in params.items() if "key" not in k.lower()}
        rf = safe_params.get("response_format")
        if isinstance(rf, type) and issubclass(rf, BaseModel):
            # with_structured_output passes the Pydantic class; show the JSON schema the API receives
            safe_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": rf.__name__, "strict": True, "schema": rf.model_json_schema()},
            }
        self._start(run_id, parent_run_id, self._name(serialized, kwargs, "chat_model"), "llm",
                    {"messages": messages[0] if len(messages) == 1 else messages}, tags, metadata,
                    model=model, extra_meta={"invocation_params": safe_params})

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        self._start(run_id, parent_run_id, self._name(serialized, kwargs, "llm"), "llm",
                    {"prompts": prompts}, tags, metadata)

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs):
        prompt = completion = reasoning = None
        outputs: list[Any] = []
        for gens in response.generations:
            for g in gens:
                msg = getattr(g, "message", None)
                outputs.append(msg if msg is not None else g.text)
                usage = getattr(msg, "usage_metadata", None) if msg is not None else None
                if usage:
                    prompt = (prompt or 0) + usage.get("input_tokens", 0)
                    completion = (completion or 0) + usage.get("output_tokens", 0)
                    r = (usage.get("output_token_details") or {}).get("reasoning")
                    if r:
                        reasoning = (reasoning or 0) + r
        if prompt is None and response.llm_output:  # fallback for older integrations
            tu = response.llm_output.get("token_usage") or {}
            prompt, completion = tu.get("prompt_tokens"), tu.get("completion_tokens")
        with self._lock:
            self.llm_calls += 1
            self.prompt_tokens += prompt or 0
            self.completion_tokens += completion or 0
            self.reasoning_tokens += reasoning or 0
        self._end(run_id, outputs[0] if len(outputs) == 1 else outputs,
                  prompt_tokens=prompt, completion_tokens=completion, reasoning_tokens=reasoning)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error=error)

    # ------------------------------------------------------------- tools / retrievers
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None,
                      inputs=None, **kwargs):
        self._start(run_id, parent_run_id, self._name(serialized, kwargs, "tool"), "tool",
                    inputs if inputs is not None else input_str, tags, metadata)

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._end(run_id, output)

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error=error)

    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, tags=None, metadata=None,
                           **kwargs):
        self._start(run_id, parent_run_id, self._name(serialized, kwargs, "retriever"), "retriever",
                    {"query": query}, tags, metadata)

    def on_retriever_end(self, documents, *, run_id, **kwargs):
        self._end(run_id, documents)

    def on_retriever_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error=error)

    # ------------------------------------------------------------- totals
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
