import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import { useUserSettings } from "./context/UserSettings";
import Admin from "./pages/Admin";
import Home from "./pages/Home";
import Settings from "./pages/Settings";

const COLLAPSE_KEY = "sidebar-collapsed";

function readCollapsed(): boolean | null {
  try {
    const v = localStorage.getItem(COLLAPSE_KEY);
    return v === null ? null : v === "1";
  } catch {
    return null;
  }
}

export default function App() {
  const { state } = useUserSettings();
  const [collapsed, setCollapsed] = useState<boolean>(() => readCollapsed() ?? false);

  // If the user never toggled on this device, follow their saved preference.
  useEffect(() => {
    if (readCollapsed() === null && state) setCollapsed(Boolean(state.values.appearance?.sidebar_collapsed));
  }, [state]);

  function toggle() {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* storage unavailable */
      }
      return !c;
    });
  }

  return (
    <div className="app">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
