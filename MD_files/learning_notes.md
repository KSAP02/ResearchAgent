# Learning Notes

One section per phase: what the concept is, how we used it, what the
experiments showed, and answers to the phase's "Think about" questions. Write
these in your own words; this is the part that sticks.

---

## Phase 1: UI shell + config sync (no LangGraph)

**Idea:** describe settings once (Pydantic models with metadata) and generate
the form, the validation and the file format from that one description.

- The backend sends `{sections: [{fields: [{type, min, max, description, ...}]}]}`;
  the UI renders whatever it receives, so a new `Field` in `config.py` appears
  on the Admin page with no frontend change.
- System settings (`config.toml`, Admin) vs user preferences (SQLite, Settings).
- Live sync: mtime-checked hot reload; mount the *directory* because single-file
  bind mounts go stale when an editor saves by replacing the file.

**Think about** (your answers):
- Which settings belong to the system and which to the user?
- Which changes are safe while live, and which need a restart or a data reset?

---

## Phase 2: LangChain fundamentals + tracing
_(to fill in)_
