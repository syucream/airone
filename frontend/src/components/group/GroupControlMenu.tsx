import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  Box,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from "@mui/material";
import { useSnackbar } from "notistack";
import { FC, useCallback } from "react";
import { Link, useNavigate } from "react-router";

import { Confirmable } from "components/common/Confirmable";
import { useTranslation } from "hooks/useTranslation";
import { aironeApiClient } from "repository/AironeApiClient";
import { groupPath, groupsPath, topPath } from "routes/Routes";

interface Props {
  groupId: number;
  anchorElem: HTMLButtonElement | null;
  handleClose: () => void;
  setToggle?: () => void;
}

export const GroupControlMenu: FC<Props> = ({
  groupId,
  anchorElem,
  handleClose,
  setToggle,
}) => {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleDelete = useCallback(async () => {
    try {
      await aironeApiClient.deleteGroup(groupId);
      enqueueSnackbar(t("group.controlMenu.deleteSuccess"), {
        variant: "success",
      });
      navigate(topPath(), { replace: true });
      navigate(groupsPath(), { replace: true });
      setToggle && setToggle();
    } catch (e) {
      enqueueSnackbar(t("group.controlMenu.deleteFailure"), {
        variant: "error",
      });
    }
  }, [navigate, enqueueSnackbar, groupId, setToggle, t]);

  return (
    <Menu
      open={Boolean(anchorElem)}
      onClose={handleClose}
      anchorEl={anchorElem}
      anchorOrigin={{
        vertical: "bottom",
        horizontal: "right",
      }}
      transformOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
    >
      <Box sx={{ width: 150 }}>
        <MenuItem component={Link} to={groupPath(groupId)}>
          <Typography>{t("group.controlMenu.editGroup")}</Typography>
        </MenuItem>
        <Confirmable
          componentGenerator={(handleOpen) => (
            <MenuItem onClick={handleOpen} sx={{ justifyContent: "end" }}>
              <ListItemText>{t("common.delete")}</ListItemText>
              <ListItemIcon>
                <DeleteOutlineIcon />
              </ListItemIcon>
            </MenuItem>
          )}
          dialogTitle={t("group.controlMenu.deleteConfirm")}
          onClickYes={handleDelete}
        />
      </Box>
    </Menu>
  );
};
