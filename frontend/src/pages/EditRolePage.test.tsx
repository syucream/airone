/**
 * @jest-environment jsdom
 */

import { Role } from "@dmm-com/airone-apiclient-typescript-fetch";
import { render } from "@testing-library/react";
import React from "react";

import { EditRolePage } from "./EditRolePage";

import { TestWrapper } from "TestWrapper";

afterEach(() => {
  jest.clearAllMocks();
});

test("should match snapshot", async () => {
  const role: Role = {
    id: 0,
    name: "",
    description: "",
    users: [],
    groups: [],
    adminUsers: [],
    adminGroups: [],
    isEditable: true,
  };

  /* eslint-disable */
  jest
    .spyOn(require("../repository/AironeApiClient").aironeApiClient, "getRole")
    .mockResolvedValue(Promise.resolve(role));
  jest
    .spyOn(require("repository/AironeApiClient").aironeApiClient, "getUsers")
    .mockResolvedValue(Promise.resolve([]));
  jest
    .spyOn(require("repository/AironeApiClient").aironeApiClient, "getGroups")
    .mockResolvedValue(Promise.resolve([]));
  /* eslint-enable */

  // wait async calls and get rendered fragment
  const result = render(<EditRolePage />, {
    wrapper: TestWrapper,
  });

  expect(result).toMatchSnapshot();
});
