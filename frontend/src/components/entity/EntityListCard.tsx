import { EntityList } from "@dmm-com/airone-apiclient-typescript-fetch";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import {
  Card,
  CardActionArea,
  CardContent,
  CardHeader,
  IconButton,
  Typography,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import React, { FC, useState } from "react";
import { Link } from "react-router-dom";

import { EntityControlMenu } from "./EntityControlMenu";

import { entityEntriesPath } from "Routes";
import { EntryImportModal } from "components/entry/EntryImportModal";

const EntityNote = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.secondary,
  display: "-webkit-box",
  overflow: "hidden",
  webkitBoxOrient: "vertical",
  webkitLineClamp: 2,
}));

const EntityName = styled(Typography)(({}) => ({
  textOverflow: "ellipsis",
  overflow: "hidden",
  whiteSpace: "nowrap",
}));

const StyledCard = styled(Card)(({}) => ({
  height: "100%",
}));

const StyledCardHeader = styled(CardHeader)(({}) => ({
  p: "0px",
  mt: "24px",
  mx: "16px",
  mb: "16px",
  ".MuiCardHeader-content": {
    width: "80%",
  },
}));

const StyledCardContent = styled(CardContent)(({}) => ({
  p: "0px",
  mt: "0px",
  mx: "16px",
  mb: "0px",
  lineHeight: 2,
}));

interface Props {
  entity: EntityList;
  setToggle?: () => void;
}

export const EntityListCard: FC<Props> = ({ entity, setToggle }) => {
  const [anchorElem, setAnchorElem] = useState<HTMLButtonElement | null>(null);
  const [openImportModal, setOpenImportModal] = React.useState(false);

  return (
    <StyledCard>
      <StyledCardHeader
        title={
          <CardActionArea component={Link} to={entityEntriesPath(entity.id)}>
            <EntityName variant="h6">{entity.name}</EntityName>
          </CardActionArea>
        }
        action={
          <>
            <IconButton
              onClick={(e) => {
                setAnchorElem(e.currentTarget);
              }}
            >
              <MoreVertIcon />
            </IconButton>
            <EntityControlMenu
              entityId={entity.id}
              anchorElem={anchorElem}
              handleClose={() => setAnchorElem(null)}
              setOpenImportModal={setOpenImportModal}
              setToggle={setToggle}
            />
          </>
        }
      />
      <StyledCardContent>
        <EntityNote>{entity.note}</EntityNote>
      </StyledCardContent>

      <EntryImportModal
        openImportModal={openImportModal}
        closeImportModal={() => setOpenImportModal(false)}
      />
    </StyledCard>
  );
};
