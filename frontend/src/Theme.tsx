import { createTheme } from "@mui/material/styles";

const baseThemeOptions = {
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 900,
      lg: 1200,
      xl: 1920,
    },
  },
  typography: {
    fontFamily: "Noto Sans JP",
  },
  components: {
    MuiMenu: {
      defaultProps: {
        disableScrollLock: true,
      },
    },
    MuiModal: {
      defaultProps: {
        disableScrollLock: true,
      },
    },
  },
} as const;

export const lightTheme = createTheme({
  ...baseThemeOptions,
  palette: {
    mode: "light",
    primary: {
      main: "#607D8B",
      dark: "#455A64",
      light: "#90A4AE",
    },
    secondary: {
      main: "#90CAF9",
    },
    success: {
      main: "#1B76D2",
    },
    error: {
      main: "#B00020",
    },
    info: {
      main: "#FFFFFF",
    },
    background: {
      default: "#F4F4F4",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#212121",
      secondary: "#455A64",
    },
    tableHeader: {
      background: "#455A64",
      text: "#FFFFFF",
    },
    tableRow: {
      alternateBackground: "#607D8B0A",
    },
    surface: {
      search: "#F4F4F4",
    },
    header: {
      versionText: "#FFFFFF8A",
    },
  },
});

export const darkTheme = createTheme({
  ...baseThemeOptions,
  palette: {
    mode: "dark",
    primary: {
      main: "#90A4AE",
      dark: "#607D8B",
      light: "#B0BEC5",
    },
    secondary: {
      main: "#90CAF9",
    },
    success: {
      main: "#42A5F5",
    },
    error: {
      main: "#CF6679",
    },
    info: {
      main: "#1E1E1E",
    },
    background: {
      default: "#121212",
      paper: "#1E1E1E",
    },
    text: {
      primary: "#E0E0E0",
      secondary: "#B0BEC5",
    },
    tableHeader: {
      background: "#263238",
      text: "#E0E0E0",
    },
    tableRow: {
      alternateBackground: "#FFFFFF0A",
    },
    surface: {
      search: "#2C2C2C",
    },
    header: {
      versionText: "#FFFFFF8A",
    },
  },
});
