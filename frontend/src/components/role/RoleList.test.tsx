/**
 * @jest-environment jsdom
 */

import { render } from "@testing-library/react";
import React from "react";

import { RoleList } from "./RoleList";

import { Role } from "@dmm-com/airone-apiclient-typescript-fetch";
import { TestWrapper } from "TestWrapper";

afterEach(() => {
  jest.clearAllMocks();
});

test("should render a component with essential props", function () {
  const roles: Role[] = [
    {
      id: 0,
      name: "",
      description: "",
      users: [],
      groups: [],
      adminUsers: [],
      adminGroups: [],
    },
  ];

  /* eslint-disable */
  jest
    .spyOn(
      require("repository/AironeApiClientV2").aironeApiClientV2,
      "getRoles"
    )
    .mockResolvedValue(Promise.resolve(roles));
  /* eslint-enable */

  expect(() => render(<RoleList />, { wrapper: TestWrapper })).not.toThrow();
});
