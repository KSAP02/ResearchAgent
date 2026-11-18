"""Admin API: read/write config/config.toml (system hyperparameters).

Two-way sync:
- UI -> file: PUT validates the changes, writes them with tomlkit (keeping
  comments and order), then hot-reloads settings.
- file -> UI: the UI polls GET (cheap), which returns the file mtime; get_settings()
  reloads automatically when the mtime changes.
"""
import tomlkit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import CONFIG_PATH, SECTION_MODELS, config_mtime, force_reload, get_settings, last_load_error
from form_schema import describe_section, validate_section_changes

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ConfigUpdate(BaseModel):
    changes: dict[str, dict]  # {"llm": {"temperature": 0.5}, ...}


def _state() -> dict:
    s = get_settings()
    mtime = config_mtime()
    return {
        "path": str(CONFIG_PATH),
        "mtime": str(mtime) if mtime is not None else None,
        "load_error": last_load_error(),
        "sections": [describe_section(k, cls, getattr(s, k)) for k, cls in SECTION_MODELS.items()],
    }


@router.get("/config")
def get_config() -> dict:
    return _state()


@router.put("/config")
def update_config(body: ConfigUpdate) -> dict:
    s = get_settings()
    errors: dict[str, str] = {}
    validated: dict[str, BaseModel] = {}

    for section, changes in body.changes.items():
        cls = SECTION_MODELS.get(section)
        if cls is None:
            errors[section] = "Unknown section"
            continue
        model, errs = validate_section_changes(cls, getattr(s, section), changes, section)
        errors.update(errs)
        if model is not None:
            validated[section] = model

    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    doc = tomlkit.parse(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else tomlkit.document()
    for section, model in validated.items():
        if section not in doc:
            doc[section] = tomlkit.table()
        dumped = model.model_dump(mode="json")
        for key in body.changes[section]:
            doc[section][key] = dumped[key]

    # Write in place (same inode) so bind mounts and open editors see the change.
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(tomlkit.dumps(doc))

    force_reload()
    return _state()
