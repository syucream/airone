import {
  Box,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Theme,
  Typography,
} from "@mui/material";
import { makeStyles } from "@mui/styles";
import React, { FC, useEffect, useState } from "react";
import { useHistory } from "react-router-dom";

import { aironeApiClientV2 } from "apiclient/AironeApiClientV2";
import { ACL } from "apiclient/autogenerated";
import { DjangoContext } from "utils/DjangoContext";

const useStyles = makeStyles<Theme>((theme) => ({
  button: {
    margin: theme.spacing(1),
  },
}));

interface Props {
  objectId: number;
  acl: ACL;
  setSubmittable: (isSubmittable: boolean) => void;
}

export const ACLForm: FC<Props> = ({ objectId, acl, setSubmittable }) => {
  const classes = useStyles();
  const history = useHistory();

  const djangoContext = DjangoContext.getInstance();
  const [isPublic, setIsPublic] = useState(acl.isPublic);
  const [defaultPermission, setDefaultPermission] = useState(
    acl.defaultPermission
  );
  // TODO correct way to collect member permissions?
  const [permissions, setPermissions] = useState(
    acl.roles.reduce((obj, role) => {
      return {
        ...obj,
        [role.id]: role,
      };
    }, {})
  );

  const checkSubmittable = () => {
    if (isPublic) {
      return true;
    }
    if (defaultPermission & djangoContext.aclTypes.full.value) {
      return true;
    }
    if (
      Object.values(permissions).some(
        (permission) =>
          permission.current_permission & djangoContext.aclTypes.full.value
      )
    ) {
      return true;
    }
    return false;
  };

  useEffect(() => {
    setSubmittable(checkSubmittable());
  });

  const handleSubmit = async () => {
    // TODO better name?
    const aclSettings = acl.members.map((member) => {
      return {
        member_id: member.id,
        member_type: member.type,
        value: permissions[member.name],
      };
    });

    await aironeApiClientV2.updateAcl(
      objectId,
      acl.name,
      acl.objtype,
      isPublic,
      acl.defaultPermission,
      aclSettings
    );

    history.go(0);
  };

  console.log("[onix(10)] permissions: ", permissions);

  return (
    <Box>
      <Table className="table table-bordered">
        <TableHead>
          <TableRow sx={{ backgroundColor: "#455A64" }}>
            <TableCell sx={{ color: "#FFFFFF" }}>項目</TableCell>
            <TableCell sx={{ color: "#FFFFFF" }}>内容</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>公開設定</TableCell>
            <TableCell>
              {/* TODO fix width */}
              <Select
                fullWidth={true}
                value={isPublic ? 1 : 0}
                onChange={(e) => setIsPublic(e.target.value === 1)}
              >
                <MenuItem value={1}>公開</MenuItem>
                <MenuItem value={0}>限定公開</MenuItem>
              </Select>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <Box>
        <Box my="32px">
          <Typography variant="h4" align="center">
            公開制限設定
          </Typography>
        </Box>

        <Table className="table table-bordered">
          <TableHead>
            <TableRow sx={{ backgroundColor: "#455A64" }}>
              <TableCell sx={{ color: "#FFFFFF" }}>ロール</TableCell>
              <TableCell sx={{ color: "#FFFFFF" }}>備考</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>全員</TableCell>
              <TableCell></TableCell>
              <TableCell>
                <Select
                  fullWidth={true}
                  value={defaultPermission}
                  onChange={(e) => setDefaultPermission(Number(e.target.value))}
                >
                  {Object.keys(djangoContext.aclTypes).map((key, index) => (
                    <MenuItem
                      key={index}
                      value={djangoContext.aclTypes[key].value}
                    >
                      {djangoContext.aclTypes[key].name}
                    </MenuItem>
                  ))}
                </Select>
              </TableCell>
            </TableRow>
            {Object.keys(permissions).map((key, index) => (
              <TableRow key={index}>
                <TableCell>{permissions[key].name}</TableCell>
                <TableCell>{permissions[key].description}</TableCell>
                <TableCell>
                  <Select
                    fullWidth={true}
                    value={permissions[key].current_permission}
                    onChange={(e) =>
                      setPermissions({
                        ...permissions,
                        [key]: {
                          ...permissions[key],
                          current_permission: e.target.value,
                        },
                      })
                    }
                  >
                    <MenuItem value={0}>(未設定)</MenuItem>
                    {Object.keys(djangoContext.aclTypes).map((key, index) => (
                      <MenuItem
                        key={index}
                        value={djangoContext.aclTypes[key].value}
                      >
                        {djangoContext.aclTypes[key].name}
                      </MenuItem>
                    ))}
                  </Select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Box>
  );
};
