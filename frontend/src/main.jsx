/*
 * The very first file the browser runs. It loads the fonts and global styles,
 * then puts the <App /> component into the empty <div id="root"> in index.html.
 * StrictMode only adds extra warnings while developing; it does nothing in production.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/instrument-sans";
import "@fontsource-variable/literata/opsz.css";
import App from "./App.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
