import { useEffect, useState } from "react";
import type { FieldValue, FormField } from "../api/client";

interface Props {
  field: FormField;
  value: FieldValue;
  onChange: (value: FieldValue) => void;
  error?: string;
  dirty?: boolean;
  disabled?: boolean;
}

/** Renders one backend-described field. The form is driven by the backend schema. */
export default function FieldInput({ field, value, onChange, error, dirty, disabled }: Props) {
  const id = `f-${field.key}`;

  const tags = (
    <>
      {field.requires_restart && <span className="tag warn">restart</span>}
      {field.phase != null && <span className="tag accent">used from phase {field.phase}</span>}
    </>
  );

  if (field.type === "bool") {
    return (
      <div className={`field${dirty ? " dirty" : ""}`}>
        <div className="field-row">
          <label className="field-label" htmlFor={id}>
            {field.label} {tags}
          </label>
          <button
            id={id}
            type="button"
            role="switch"
            aria-checked={Boolean(value)}
            className="switch"
            disabled={disabled}
            onClick={() => onChange(!value)}
          />
        </div>
        {field.description && <span className="field-desc">{field.description}</span>}
        {error && <span className="field-error">{error}</span>}
      </div>
    );
  }

  return (
    <div className={`field${dirty ? " dirty" : ""}`}>
      <label className="field-label" htmlFor={id}>
        {field.label} {tags}
      </label>
      {field.type === "enum" ? (
        <select id={id} value={String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          {(field.options ?? []).map((o) => (
            <option key={String(o)} value={String(o)}>
              {String(o)}
            </option>
          ))}
        </select>
      ) : field.type === "int" || field.type === "float" ? (
        <NumberInput id={id} field={field} value={value} disabled={disabled} onChange={onChange} />
      ) : (
        <input
          id={id}
          type="text"
          value={String(value)}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {field.description && <span className="field-desc">{field.description}</span>}
      {field.danger && <span className="field-desc" style={{ color: "var(--warn)" }}>{field.danger}</span>}
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}

/** Keeps the raw text while typing; reports a number when parseable, otherwise the raw
 *  text (the backend then returns a validation error for that field). */
function NumberInput({
  id,
  field,
  value,
  disabled,
  onChange,
}: {
  id: string;
  field: FormField;
  value: FieldValue;
  disabled?: boolean;
  onChange: (v: FieldValue) => void;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => {
    if (Number(text) !== Number(value)) setText(String(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const step = field.step ?? (field.type === "int" ? 1 : 0.01);
  return (
    <input
      id={id}
      type="number"
      value={text}
      step={step}
      min={field.min ?? undefined}
      max={field.max ?? undefined}
      disabled={disabled}
      onChange={(e) => {
        const raw = e.target.value;
        setText(raw);
        const n = field.type === "int" ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
        onChange(raw.trim() !== "" && Number.isFinite(n) ? n : raw);
      }}
    />
  );
}
