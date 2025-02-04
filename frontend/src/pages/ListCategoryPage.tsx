import AddIcon from "@mui/icons-material/Add";
import { Box, Button, Container, Grid, List, ListItem, ListItemText, Typography } from "@mui/material";
import React, { FC, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AironeBreadcrumbs } from "components/common/AironeBreadcrumbs";
import { usePage } from "hooks/usePage";
import { useTypedParams } from "../hooks/useTypedParams";

import { PageHeader } from "components/common/PageHeader";
import { SearchBox } from "components/common/SearchBox";
import { useAsyncWithThrow } from "hooks";
import { aironeApiClient } from "repository";
import { newCategoryPath, topPath } from "routes/Routes";
import { normalizeToMatch } from "services/StringUtil";
import { CategoryListHeader } from "components/category/CategoryListHeader";

interface Props {
}

export const ListCategoryPage: FC<Props> = ({ }) => {
  const navigate = useNavigate();
  const { categoryId } = useTypedParams<{ categoryId: number }>();

  const [openImportModal, setOpenImportModal] = React.useState(false);
  const [toggle, setToggle] = useState(false);

  // variable to store search query
  const [query, setQuery] = useState("");
  const [page, changePage] = usePage();

  // request handler when user specify query
  const handleChangeQuery = (newQuery?: string) => {
    changePage(1);
    setQuery(newQuery ?? "");

    navigate({
      pathname: location.pathname,
      search: newQuery ? `?query=${newQuery}` : "",
    });
  };

  const categories = useAsyncWithThrow(async () => {
    return await aironeApiClient.getCategories();
  }, [toggle]);

  return (
    <Box>
      <AironeBreadcrumbs>
        <Typography component={Link} to={topPath()}>
          Top
        </Typography>
        <Typography color="textPrimary">カテゴリ一覧</Typography>
      </AironeBreadcrumbs>

      <PageHeader
        title={"カテゴリ一覧"}
      >
      </PageHeader>
      <Container>
        {/* Show control menus to filter and create category */}
        <Box display="flex" justifyContent="space-between" mb="16px">
          <Box width="600px">
            <SearchBox
              placeholder="カテゴリを絞り込む"
              defaultValue={query}
              onKeyPress={(e) => {
                e.key === "Enter" &&
                  handleChangeQuery(
                    normalizeToMatch((e.target as HTMLInputElement).value ?? "")
                  );
              }}
            />
          </Box>
          <Button
            variant="contained"
            color="secondary"
            component={Link}
            to={newCategoryPath()}
            sx={{ height: "48px", borderRadius: "24px" }}
          >
            <AddIcon /> 新規カテゴリを作成
          </Button>
        </Box>

        {/* Context of Category */}
        <Grid container spacing={3}>
          {categories.value?.results.map((category) => (
            <Grid item md={4}>
              <List
                subheader={
                  <CategoryListHeader
                    category={category}
                    setOpenImportModal={setOpenImportModal}
                    setToggle={() => setToggle(!toggle)}
                  />
                }
              >
                {category.models.map((models) => (
                  <ListItem button component={Link} to={`/categories/${category.id}/entities`}>
                    <ListItemText primary={models.name} />
                  </ListItem>
                ))}
              </List>
            </Grid>
          ))}
        </Grid>

      </Container>
    </Box>
  );
};