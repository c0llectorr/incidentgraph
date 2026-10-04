import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
// highlight.js token colors first, so our palette overrides in globals.css win.
import "highlight.js/styles/github.css";
import "./styles/tokens.css";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
