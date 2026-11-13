import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import ErrorOutlinedIcon from "@mui/icons-material/ErrorOutlined";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { styled } from "@mui/material/styles";
import { MaterialDesignContent, SnackbarProvider } from "notistack";
import { FC, ReactNode } from "react";

// Notistack's default success, warning, and info backgrounds do not provide
// 4.5:1 contrast with its white message text.
const SnackbarContent = styled(MaterialDesignContent)({
  "&.notistack-MuiContent-success": { backgroundColor: "#2e7d32" },
  "&.notistack-MuiContent-warning": { backgroundColor: "#8a5700" },
  "&.notistack-MuiContent-info": { backgroundColor: "#01579b" },
});

export const AironeSnackbarProvider: FC<{ children: ReactNode }> = ({
  children,
}) => {
  return (
    <SnackbarProvider
      maxSnack={5}
      Components={{
        success: SnackbarContent,
        warning: SnackbarContent,
        info: SnackbarContent,
      }}
      iconVariant={{
        success: (
          <CheckCircleOutlineOutlinedIcon
            sx={{ fontSize: "20px", mr: "8px" }}
          />
        ),
        error: <ErrorOutlinedIcon sx={{ fontSize: "20px", mr: "8px" }} />,
        warning: (
          <WarningAmberOutlinedIcon sx={{ fontSize: "20px", mr: "8px" }} />
        ),
        info: <InfoOutlinedIcon sx={{ fontSize: "20px", mr: "8px" }} />,
      }}
    >
      {children}
    </SnackbarProvider>
  );
};
