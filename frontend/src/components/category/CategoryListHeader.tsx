import MoreVertIcon from "@mui/icons-material/MoreVert";
import TurnedInTwoToneIcon from "@mui/icons-material/TurnedInTwoTone";
import { Box, IconButton, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { FC, useState } from "react";

import { CategoryList } from "@dmm-com/airone-apiclient-typescript-fetch";
import { CategoryControlMenu } from "components/category/CategoryControlMenu";
import { BetweenAlignedBox, FlexBox } from "components/common/FlexBox";
import { ServerContext } from "services";
import { canEdit } from "services/ACLUtil";

interface Props {
  category: CategoryList;
  setToggle: () => void;
}

export const CategoryListHeader: FC<Props> = ({ category, setToggle }) => {
  const theme = useTheme();
  const [categoryAnchorEl, setCategoryAnchorEl] =
    useState<HTMLButtonElement | null>(null);

  const isReadonly = ServerContext.getInstance()?.user?.isReadonly ?? false;

  return (
    <BetweenAlignedBox>
      {/* Category image */}
      <FlexBox alignItems="center">
        <Box mr="8px" p="4px" height="24px" width="24px">
          <TurnedInTwoToneIcon sx={{ color: theme.palette.text.secondary }} />
        </Box>

        {/* Category title */}
        <Typography variant="h6" component="div">
          {category.name}
        </Typography>
      </FlexBox>

      {/* Category control menu */}
      {!isReadonly && canEdit(category.permission) && (
        <FlexBox sx={{ marginInlineStart: "40px" }}>
          <IconButton
            onClick={(e) => {
              setCategoryAnchorEl(e.currentTarget);
            }}
          >
            <MoreVertIcon fontSize="small" />
          </IconButton>
          <CategoryControlMenu
            categoryId={category.id}
            anchorElem={categoryAnchorEl}
            handleClose={() => setCategoryAnchorEl(null)}
            setToggle={setToggle}
            permission={category.permission}
          />
        </FlexBox>
      )}
    </BetweenAlignedBox>
  );
};
