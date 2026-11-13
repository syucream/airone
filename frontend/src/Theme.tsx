import { createTheme } from "@mui/material/styles";
export const theme = createTheme({
  palette: {
    primary: {
      main: "#546E7A",
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
    warning: {
      main: "#ED6C02",
      light: "#FF9800",
      dark: "#8A5700",
    },
    info: {
      main: "#FFFFFF",
    },
    background: {
      default: "#607D8B",
    },
  },
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
});
