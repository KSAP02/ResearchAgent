"""Per-user preferences (stored in SQLite, not config.toml).

System hyperparameters belong in config.toml (Admin page). Things a *user* picks
for themselves (appearance, report style, review steps) belong here. The
`phase` extra marks preferences that are stored now but used by a later phase.
"""
from typing import Literal

from pydantic import BaseModel, Field


class AppearanceSettings(BaseModel):
    """How the app looks."""

    theme: Literal["system", "light", "dark"] = Field("system", description="Colour theme.")
    font_size: Literal["small", "medium", "large"] = Field("medium", description="Base text size.")
    density: Literal["comfortable", "compact"] = Field("comfortable", description="Spacing between elements.")
    sidebar_collapsed: bool = Field(False, description="Start with the sidebar collapsed.")


class ResearchPreferences(BaseModel):
    """Defaults for your research runs."""

    report_length: Literal["brief", "standard", "detailed"] = Field(
        "standard", description="How long the final report should be.", json_schema_extra={"phase": 10})
    citation_style: Literal["numeric", "author_year"] = Field(
        "numeric", description="Citation format in reports.", json_schema_extra={"phase": 10})
    review_plan_before_research: bool = Field(
        False, description="Pause after planning so you can approve or edit the queries.", json_schema_extra={"phase": 8})
    show_trace_details: bool = Field(
        False, description="Show node-by-node details of each run.", json_schema_extra={"phase": 9})


USER_SECTION_MODELS: dict[str, type[BaseModel]] = {
    "appearance": AppearanceSettings,
    "research": ResearchPreferences,
}


class UserSettings(BaseModel):
    appearance: AppearanceSettings = AppearanceSettings()
    research: ResearchPreferences = ResearchPreferences()
