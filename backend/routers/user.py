"""User settings API (per-user preferences in SQLite)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.sqlite import load_user_settings, save_user_settings
from form_schema import describe_section, validate_section_changes
from user_settings import USER_SECTION_MODELS, UserSettings

router = APIRouter(prefix="/api/user", tags=["user"])

DEFAULT_USER = "default"  # single-user for now


class SettingsUpdate(BaseModel):
    changes: dict[str, dict]


def _current() -> UserSettings:
    raw = load_user_settings(DEFAULT_USER)
    try:
        return UserSettings.model_validate(raw or {})
    except Exception:
        return UserSettings()  # stored data no longer valid -> defaults


def _state(settings: UserSettings) -> dict:
    return {
        "values": settings.model_dump(mode="json"),
        "sections": [describe_section(k, cls, getattr(settings, k)) for k, cls in USER_SECTION_MODELS.items()],
    }


@router.get("/settings")
def get_user_settings() -> dict:
    return _state(_current())


@router.put("/settings")
def update_user_settings(body: SettingsUpdate) -> dict:
    current = _current()
    errors: dict[str, str] = {}
    data = current.model_dump()
    for section, changes in body.changes.items():
        cls = USER_SECTION_MODELS.get(section)
        if cls is None:
            errors[section] = "Unknown section"
            continue
        model, errs = validate_section_changes(cls, getattr(current, section), changes, section)
        errors.update(errs)
        if model is not None:
            data[section] = model.model_dump()
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    updated = UserSettings.model_validate(data)
    save_user_settings(DEFAULT_USER, updated.model_dump(mode="json"))
    return _state(updated)
