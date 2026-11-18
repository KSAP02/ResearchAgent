import FieldInput from "../components/FieldInput";
import { useUserSettings } from "../context/UserSettings";

/** Per-user preferences. Saved automatically (SQLite on the backend). */
export default function Settings() {
  const { state, error, update } = useUserSettings();

  if (!state) {
    return <div className="page status-text">{error ? `Could not load settings: ${error}` : "Loading..."}</div>;
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Settings</h1>
        <p>Your personal preferences. Changes save automatically.</p>
      </div>

      {error && <div className="banner error">{error}</div>}

      {state.sections.map((section) => (
        <section className="card" key={section.key}>
          <div className="card-head">
            <h2>{section.title}</h2>
            {section.description && <p>{section.description}</p>}
          </div>
          <div className="fields">
            {section.fields
              .filter(
                (f) =>
                  !f.visible_when ||
                  Object.entries(f.visible_when).every(
                    ([k, v]) => String(state.values[section.key]?.[k]) === String(v),
                  ),
              )
              .map((f) => (
              <FieldInput
                key={`${section.key}.${f.key}`}
                field={f}
                value={state.values[section.key]?.[f.key] ?? f.value}
                onChange={(v) => void update(section.key, f.key, v)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
