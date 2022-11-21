import MoreVertIcon from "@mui/icons-material/MoreVert";
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  CardHeader,
  Grid,
  IconButton,
  Pagination,
  Stack,
  Theme,
  Typography,
} from "@mui/material";
import { makeStyles } from "@mui/styles";
import React, { FC, useState } from "react";
import { Link } from "react-router-dom";

import { entityEntriesPath } from "Routes";
import { EntityList as EntityListInterface } from "apiclient/autogenerated";
import { SearchBox } from "components/common/SearchBox";
import { EntityControlMenu } from "components/entity/EntityControlMenu";
import { EntryImportModal } from "components/entry/EntryImportModal";
import { normalizeToMatch } from "utils/StringUtil";

const useStyles = makeStyles<Theme>((theme) => ({
  button: {
    margin: theme.spacing(1),
  },
  entityName: {
    margin: theme.spacing(1),
  },
  entityNote: {
    color: theme.palette.text.secondary,
    display: "-webkit-box",
    overflow: "hidden",
    "-webkit-box-orient": "vertical",
    "-webkit-line-clamp": 2,
  },
}));

interface Props {
  entities: EntityListInterface[];
  page: number;
  query?: string;
  maxPage: number;
  handleChangePage: (page: number) => void;
  handleChangeQuery: (query: string) => void;
}

export const EntityList: FC<Props> = ({
  entities,
  page,
  query,
  maxPage,
  handleChangePage,
  handleChangeQuery,
}) => {
  const classes = useStyles();

  const [keyword, setKeyword] = useState(query ?? "");
  const [entityAnchorEls, setEntityAnchorEls] = useState<{
    [key: number]: HTMLButtonElement;
  } | null>({});
  const [openImportModal, setOpenImportModal] = React.useState(false);

  return (
    <Box>
      {/* This box shows search box and create button */}
      <Box display="flex" justifyContent="space-between" mb={8}>
        <Box className={classes.search} width={500}>
          <SearchBox
            placeholder="エンティティ名で絞り込む"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter") {
                handleChangeQuery(
                  keyword.length > 0 ? normalizeToMatch(keyword) : undefined
                );
              }
            }}
          />
        </Box>
      </Box>

      {/* This box shows each entity Cards */}
      <Grid container spacing={2}>
        {entities.map((entity) => (
          <Grid item xs={4} key={entity.id}>
            <Card sx={{ height: "100%" }}>
              <CardHeader
                sx={{
                  p: "0px",
                  mt: "24px",
                  mx: "16px",
                  mb: "16px",
                  ".MuiCardHeader-content": {
                    width: "80%",
                  },
                }}
                title={
                  <CardActionArea
                    component={Link}
                    to={entityEntriesPath(entity.id)}
                  >
                    <Typography
                      variant="h6"
                      sx={{
                        textOverflow: "ellipsis",
                        overflow: "hidden",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {entity.name}
                    </Typography>
                  </CardActionArea>
                }
                action={
                  <>
                    <IconButton
                      onClick={(e) => {
                        setEntityAnchorEls({
                          ...entityAnchorEls,
                          [entity.id]: e.currentTarget,
                        });
                      }}
                    >
                      <MoreVertIcon />
                    </IconButton>
                    <EntityControlMenu
                      entityId={entity.id}
                      anchorElem={entityAnchorEls[entity.id]}
                      handleClose={(entityId: number) =>
                        setEntityAnchorEls({
                          ...entityAnchorEls,
                          [entityId]: null,
                        })
                      }
                      setOpenImportModal={setOpenImportModal}
                    />
                  </>
                }
              />
              <CardContent
                sx={{
                  p: "0px",
                  mt: "0px",
                  mx: "16px",
                  mb: "0px",
                  lineHeight: 2,
                }}
              >
                <Typography className={classes.entityNote}>
                  {entity.note}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Box display="flex" justifyContent="center" my="30px">
        <Stack spacing={2}>
          <Pagination
            count={maxPage}
            page={page}
            onChange={(e, page) => handleChangePage(page)}
            color="primary"
          />
        </Stack>
      </Box>

      <EntryImportModal
        openImportModal={openImportModal}
        closeImportModal={() => setOpenImportModal(false)}
      />
    </Box>
  );
};
