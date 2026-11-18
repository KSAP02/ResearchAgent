import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { UserSettingsProvider } from "./context/UserSettings";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <UserSettingsProvider>
        <App />
      </UserSettingsProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
