import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AironeSnackbarProvider } from "AironeSnackbarProvider";
import { AppBase } from "AppBase";
import { ThemeContextProvider } from "ThemeContext";

const container = document.getElementById("app");
if (container == null) {
  throw new Error("failed to initializer React app.");
}
const root = createRoot(container);
root.render(
  <StrictMode>
    <ThemeContextProvider>
      <AironeSnackbarProvider>
        <AppBase />
      </AironeSnackbarProvider>
    </ThemeContextProvider>
  </StrictMode>,
);
