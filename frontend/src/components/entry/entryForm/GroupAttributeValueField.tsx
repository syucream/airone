import { FC } from "react";

import { aironeApiClient } from "../../../repository/AironeApiClient";

import {
  GroupOrRoleAttributeValueField,
  GroupOrRoleFieldProps,
} from "./GroupOrRoleAttributeValueField";

const loadGroups = async (query?: string) =>
  (await aironeApiClient.getGroups(1, query)).results ?? [];

export const GroupAttributeValueField: FC<GroupOrRoleFieldProps> = (props) => (
  <GroupOrRoleAttributeValueField
    {...props}
    kind="group"
    loadOptions={loadGroups}
  />
);
