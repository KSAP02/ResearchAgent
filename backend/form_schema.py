"""Turn Pydantic models into a simple form description the frontend renders.

Both the Admin page (config.toml) and the Settings page (user preferences) use
this, so adding a field to a model is enough to make it appear in the UI.
"""
from typing import Literal, get_args, get_origin

import annotated_types as at
from pydantic import BaseModel


def _field_type(annotation) -> tuple[str, list | None]:
    if get_origin(annotation) is Literal:
        return "enum", list(get_args(annotation))
    if annotation is bool:
        return "bool", None
    if annotation is int:
        return "int", None
    if annotation is float:
        return "float", None
    return "str", None


def describe_fields(model_cls: type[BaseModel], values: BaseModel) -> list[dict]:
    fields = []
    for name, info in model_cls.model_fields.items():
        ftype, options = _field_type(info.annotation)
        minimum = maximum = None
        for m in info.metadata:
            if isinstance(m, at.Ge):
                minimum = m.ge
            elif isinstance(m, at.Gt):
                minimum = m.gt
            elif isinstance(m, at.Le):
                maximum = m.le
            elif isinstance(m, at.Lt):
                maximum = m.lt
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        fields.append(
            {
                "key": name,
                "label": extra.get("label") or name.replace("_", " ").capitalize(),
                "type": ftype,
                "options": options,
                "min": minimum,
                "max": maximum,
                "step": extra.get("step"),
                "description": info.description or "",
                "default": info.default,
                "value": getattr(values, name),
                "requires_restart": bool(extra.get("requires_restart", False)),
                "danger": extra.get("danger"),
                "phase": extra.get("phase"),
                # {"other_field": value}: UI shows this field only when the sibling matches
                "visible_when": extra.get("visible_when"),
            }
        )
    return fields


ACRONYMS = {"llm": "LLM"}


def describe_section(key: str, model_cls: type[BaseModel], values: BaseModel) -> dict:
    doc = (model_cls.__doc__ or "").strip()
    return {
        "key": key,
        "title": ACRONYMS.get(key, key.replace("_", " ").title()),
        "description": doc,
        "fields": describe_fields(model_cls, values),
    }


def validate_section_changes(model_cls: type[BaseModel], current: BaseModel, changes: dict, prefix: str):
    """Merge changes into current values and validate. Returns (model | None, errors)."""
    errors: dict[str, str] = {}
    unknown = set(changes) - set(model_cls.model_fields)
    for k in unknown:
        errors[f"{prefix}.{k}"] = "Unknown setting"
    if unknown:
        return None, errors
    from pydantic import ValidationError

    try:
        return model_cls.model_validate({**current.model_dump(), **changes}), {}
    except ValidationError as exc:
        for e in exc.errors():
            loc = ".".join(str(p) for p in e["loc"])
            errors[f"{prefix}.{loc}"] = e["msg"]
        return None, errors
