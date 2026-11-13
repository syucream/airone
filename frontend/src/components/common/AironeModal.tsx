import { Box, Modal, Typography } from "@mui/material";
import { styled } from "@mui/material/styles";
import { FC, ReactNode, useId } from "react";

const StyledModal = styled(Modal)(({}) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}));

const Paper = styled(Box)(({ theme }) => ({
  position: "relative",
  display: "flex",
  flexDirection: "column",
  boxSizing: "border-box",
  maxHeight: "calc(100vh - 32px)",
  backgroundColor: theme.palette.background.paper,
  border: "2px solid #000",
  boxShadow: theme.shadows[5],
  padding: theme.spacing(2, 3, 1),
  width: "50%",
}));

interface Props {
  title: string;
  description?: string;
  caption?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export const AironeModal: FC<Props> = ({
  title,
  description,
  caption,
  open,
  onClose,
  children,
}) => {
  const labelId = useId();
  return (
    <StyledModal open={open} onClose={onClose}>
      <Paper
        id="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${labelId}-title`}
        aria-describedby={description ? `${labelId}-description` : undefined}
      >
        <Typography id={`${labelId}-title`} variant={"h6"} my="8px">
          {title}
        </Typography>
        {description && (
          <Typography id={`${labelId}-description`} variant={"body2"} my="4px">
            {description}
          </Typography>
        )}
        {caption && (
          <Typography variant={"caption"} my="4px">
            {caption}
          </Typography>
        )}

        <Box sx={{ minHeight: 0, overflowY: "auto" }}>{children}</Box>
      </Paper>
    </StyledModal>
  );
};
