/**
 * @jest-environment jsdom
 */

import { EntryAttributeTypeTypeEnum } from "@dmm-com/airone-apiclient-typescript-fetch";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";

import { AttrStatsModal } from "./AttrStatsModal";

import { TestWrapperWithoutRoutes } from "TestWrapper";
import i18n from "i18n/config";
import { aironeApiClient } from "repository/AironeApiClient";

jest.mock("repository/AironeApiClient");

const mockAdvancedSearch = aironeApiClient.advancedSearch as jest.Mock;

const renderComponent = async (props: {
  open: boolean;
  onClose: () => void;
  attrname: string;
  attrType: number;
  totalCount: number;
}) => {
  const router = createMemoryRouter([
    {
      path: "/",
      element: <AttrStatsModal {...props} />,
    },
  ]);

  await act(async () => {
    render(<RouterProvider router={router} />, {
      wrapper: TestWrapperWithoutRoutes,
    });
  });
};

beforeEach(() => {
  jest.clearAllMocks();
  mockAdvancedSearch.mockResolvedValue({
    count: 1,
    values: [
      {
        entry: { id: 1, name: "entry1" },
        attrs: {
          attr1: {
            isReadable: true,
            value: { asString: "value1" },
          },
        },
      },
    ],
  });
});

test("should render aggregation title and table headers", async () => {
  await renderComponent({
    open: true,
    onClose: jest.fn(),
    attrname: "attr1",
    attrType: EntryAttributeTypeTypeEnum.STRING,
    totalCount: 1,
  });

  await waitFor(() => {
    expect(screen.getByText("値")).toBeInTheDocument();
  });

  expect(screen.getByText("「attr1」の集計")).toBeInTheDocument();
  expect(screen.getByText("件数")).toBeInTheDocument();
});

test("renders in English", async () => {
  await act(async () => {
    await i18n.changeLanguage("en");
  });

  await renderComponent({
    open: true,
    onClose: jest.fn(),
    attrname: "attr1",
    attrType: EntryAttributeTypeTypeEnum.STRING,
    totalCount: 1,
  });

  await waitFor(() => {
    expect(screen.getByText("Value")).toBeInTheDocument();
  });

  expect(screen.getByText("Aggregation of “attr1”")).toBeInTheDocument();
  expect(screen.getByText("Count")).toBeInTheDocument();
});
