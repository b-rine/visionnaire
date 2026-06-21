import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { installApiKeyInterceptors } from "./apiKey";
import "./index.css";

installApiKeyInterceptors();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
