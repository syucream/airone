import { ThemeProvider } from "@mui/material/styles";
import { SnackbarProvider } from "notistack";
import { FC, ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { SWRConfig } from "swr";

import { lightTheme } from "./Theme";

export const TestWrapper: FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ThemeProvider theme={lightTheme}>
        <SnackbarProvider maxSnack={1} autoHideDuration={100}>
          <MemoryRouter>{children}</MemoryRouter>
        </SnackbarProvider>
      </ThemeProvider>
    </SWRConfig>
  );
};

export const TestWrapperWithoutRoutes: FC<{ children: ReactNode }> = ({
  children,
}) => {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ThemeProvider theme={lightTheme}>
        <SnackbarProvider maxSnack={1} autoHideDuration={100}>
          {children}
        </SnackbarProvider>
      </ThemeProvider>
    </SWRConfig>
  );
};
