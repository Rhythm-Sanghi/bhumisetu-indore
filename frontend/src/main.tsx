import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "ol/ol.css";
import "./tokens.css";
import "./styles.css";
import "./case-layout.css";

const redirectTo = import.meta.env.VITE_APP_REDIRECT;
if (redirectTo && window.location.origin !== redirectTo) {
  window.location.replace(redirectTo);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
