import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type AdminConfig, type Changes, type FieldValue } from "../api/client";
import FieldInput from "../components/FieldInput";

const POLL_MS = 4000;

function fmtMtime(mtime: string | null): string {
  if (!mtime) return "file not found";
  try {
    return new Date(Number(BigInt(mtime) / 1000000n)).toLocaleString();
  } catch {
    return mtime;
  }
}

/** System hyperparameters, two-way synced with config/config.toml. */
export default function Admin() {
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [draft, setDraft] = useState<Record<string, FieldValue>>({}); // "section.key" -> value
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [externalChange, setExternalChange] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const mtimeRef = useRef<string | null>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  const apply = useCallback((c: AdminConfig) => {
    setConfig(c);
    mtimeRef.current = c.mtime;
  }, []);

  // Initial load + file -> UI sync (poll + on focus).
  useEffect(() => {
    let alive = true;
    const check = async (initial = false) => {
      try {
        const c = await api.getAdminConfig();
        if (!alive) return;
        setLoadError(null);
        if (initial || mtimeRef.current === null) {
          apply(c);
        } else if (c.mtime !== mtimeRef.current) {
          if (Object.keys(draftRef.current).length === 0) {
            apply(c);
            setNotice("Reloaded: config.toml changed on disk.");
          } else {
            setExternalChange(true);
          }
        } else {
          setConfig((prev) => (prev && prev.load_error !== c.load_error ? { ...prev, load_error: c.load_error } : prev));
        }
      } catch (e) {
        if (alive) setLoadError(e instanceof Error ? e.message : String(e));
      }
    };
    void check(true);
    const id = window.setInterval(() => void check(), POLL_MS);
    const onFocus = () => void check();
    window.addEventListener("focus", onFocus);
    return () => {
      alive = false;
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [apply]);

  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(t);
  }, [notice]);

  if (loadError && !config) {
    return (
      <div className="page">
        <div className="banner error">Could not load config: {loadError}</div>
      </div>
    );
  }
  if (!config) return <div className="page status-text">Loading...</div>;

  const dirtyKeys = Object.keys(draft);

  function setField(section: string, key: string, original: FieldValue, value: FieldValue) {
    const k = `${section}.${key}`;
    setDraft((d) => {
      const next = { ...d };
      if (value === original) delete next[k];
      else next[k] = value;
      return next;
    });
    setErrors((e) => {
      const { [k]: _removed, ...rest } = e;
      return rest;
    });
  }

  async function reloadFromFile() {
    const c = await api.getAdminConfig();
    apply(c);
    setDraft({});
    setErrors({});
    setExternalChange(false);
  }

  async function save() {
    if (!config) return;
    const risky = config.sections.flatMap((s) =>
      s.fields
        .filter((f) => `${s.key}.${f.key}` in draft && (f.requires_restart || f.danger))
        .map((f) => `• ${s.title} → ${f.label}${f.danger ? `: ${f.danger}` : " (requires restart)"}`),
    );
    if (risky.length && !window.confirm(`These changes need care:\n\n${risky.join("\n")}\n\nSave anyway?`)) return;

    const changes: Changes = {};
    for (const [k, v] of Object.entries(draft)) {
      const [section, key] = k.split(".");
      (changes[section] ??= {})[key] = v;
    }
    setSaving(true);
    try {
      apply(await api.updateAdminConfig(changes));
      setDraft({});
      setErrors({});
      setExternalChange(false);
      setNotice(`Saved ${dirtyKeys.length} change${dirtyKeys.length === 1 ? "" : "s"} to config.toml.`);
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fieldErrors).length) setErrors(e.fieldErrors);
      else setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Admin</h1>
        <p>System hyperparameters, synced both ways with config.toml. Changes apply to the next run.</p>
      </div>

      <div className="meta">
        <span>
          File: <code>{config.path}</code>
        </span>
        <span>Last modified: {fmtMtime(config.mtime)}</span>
      </div>

      {config.load_error && (
        <div className="banner error">
          <div>
            config.toml currently has an error, so the last valid settings are still in use.
            <pre>{config.load_error}</pre>
          </div>
        </div>
      )}
      {externalChange && (
        <div className="banner warn">
          <span>config.toml was changed outside this page while you have unsaved edits.</span>
          <button className="btn" onClick={() => void reloadFromFile()}>
            Load file version
          </button>
        </div>
      )}
      {notice && <div className="banner info">{notice}</div>}

      {config.sections.map((section) => (
        <section className="card" key={section.key}>
          <div className="card-head">
            <h2>{section.title}</h2>
            {section.description && <p>{section.description}</p>}
          </div>
          <div className="fields">
            {section.fields.map((f) => {
              const k = `${section.key}.${f.key}`;
              const dirty = k in draft;
              return (
                <FieldInput
                  key={k}
                  field={f}
                  value={dirty ? draft[k] : f.value}
                  dirty={dirty}
                  error={errors[k]}
                  onChange={(v) => setField(section.key, f.key, f.value, v)}
                />
              );
            })}
          </div>
        </section>
      ))}

      {dirtyKeys.length > 0 && (
        <div className="save-bar">
          <span className="status-text">
            {dirtyKeys.length} unsaved change{dirtyKeys.length === 1 ? "" : "s"}
          </span>
          <div className="actions">
            <button
              className="btn"
              onClick={() => {
                setDraft({});
                setErrors({});
              }}
              disabled={saving}
            >
              Discard
            </button>
            <button className="btn primary" onClick={() => void save()} disabled={saving}>
              {saving ? "Saving..." : "Save to config.toml"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
