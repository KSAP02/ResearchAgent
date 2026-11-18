import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, type FieldValue, type UserSettingsState } from "../api/client";

interface Ctx {
  state: UserSettingsState | null;
  error: string | null;
  update: (section: string, key: string, value: FieldValue) => Promise<void>;
}

const UserSettingsContext = createContext<Ctx | null>(null);

/** Applies appearance preferences to <html> so CSS tokens pick them up. */
function applyAppearance(state: UserSettingsState | null) {
  const a = state?.values.appearance;
  const root = document.documentElement;
  const theme = String(a?.theme ?? "system");
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  root.setAttribute("data-font", String(a?.font_size ?? "medium"));
  root.setAttribute("data-density", String(a?.density ?? "comfortable"));
}

export function UserSettingsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UserSettingsState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getUserSettings()
      .then(setState)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => applyAppearance(state), [state]);

  const update = useCallback(async (section: string, key: string, value: FieldValue) => {
    // optimistic: apply immediately, then persist
    setState((prev) =>
      prev ? { ...prev, values: { ...prev.values, [section]: { ...prev.values[section], [key]: value } } } : prev,
    );
    try {
      setState(await api.updateUserSettings({ [section]: { [key]: value } }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState(await api.getUserSettings());
    }
  }, []);

  return <UserSettingsContext.Provider value={{ state, error, update }}>{children}</UserSettingsContext.Provider>;
}

export function useUserSettings(): Ctx {
  const ctx = useContext(UserSettingsContext);
  if (!ctx) throw new Error("useUserSettings must be used inside UserSettingsProvider");
  return ctx;
}
