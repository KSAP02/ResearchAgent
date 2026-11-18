# Phase 1: UI shell, Admin config sync, user Settings ✅

**Date:** 2026-11-18

## Built
- **Frontend:** matte light/dark design tokens, collapsible sidebar
  (`react-router`), Home (question bar + examples + result), Admin (form
  generated from the backend config schema, save bar, inline errors,
  confirmations, external-change banner), Settings (auto-save; theme/font/density applied live).
- **Backend:** `config/config.toml` with a read-write directory mount;
  mtime-based hot reload; `tomlkit` in-place writes; `form_schema.py`;
  `/api/admin/config`, `/api/user/settings`; `user_settings` table.
- `.env` lists the OpenAI / LangSmith / Semantic Scholar variables.

## Database changes
New `user_settings` table. See `MD_files/database.md`.

## Tests
UI → file write (comments kept), in-place and replace-on-save edits picked up
live, 422 field errors, broken file keeps last good settings, user settings
persist across restart, all routes 200, screenshots in both themes.

## Decisions
- System hyperparameters → `config.toml` (Admin); user preferences → SQLite (Settings).
- Mount the `config/` directory, not the file (single-file mounts go stale).
- Forms are generated from Pydantic models, so later phases only add `Field`s.
