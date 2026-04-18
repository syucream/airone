import { Box, Button, Typography } from "@mui/material";
import { FC } from "react";

import { loginPath } from "../routes/Routes";

import { aironeApiClient } from "repository/AironeApiClient";

export const NonTermsServiceAgreementPage: FC = () => {
  const handleLogout = async () => {
    await aironeApiClient.postLogout();
    window.location.href = `${loginPath()}?next=${window.location.pathname}`;
  };

  return (
    <Box
      display="flex"
      flexDirection="column"
      flexGrow={1}
      alignItems="center"
      justifyContent="center"
    >
      <Box display="flex" my="52px">
        <Typography
          id="sorry_notfound"
          variant="h1"
          color="text.disabled"
          fontWeight="bold"
        >
          :;(∩´﹏`∩);:
        </Typography>
      </Box>
      <Typography color="text.secondary">
        ご利用をされるにはサービス規約への同意が必要です。
      </Typography>
      <Box>
        <Button
          variant="contained"
          color="secondary"
          sx={{ borderRadius: "16px", my: "40px" }}
          onClick={() => handleLogout()}
        >
          規約同意ページに戻る
        </Button>
      </Box>
    </Box>
  );
};
