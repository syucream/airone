import { FC } from "react";

import { aironeApiClient } from "../../../repository/AironeApiClient";

import {
  GroupOrRoleAttributeValueField,
  GroupOrRoleFieldProps,
} from "./GroupOrRoleAttributeValueField";

const loadRoles = (query?: string) => aironeApiClient.getRoles(query);

export const RoleAttributeValueField: FC<GroupOrRoleFieldProps> = (props) => (
  <GroupOrRoleAttributeValueField
    {...props}
    kind="role"
    loadOptions={loadRoles}
  />
);
