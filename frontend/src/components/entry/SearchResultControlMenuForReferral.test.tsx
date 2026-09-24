/**
 * @jest-environment jsdom
 */

import { act, render, screen } from "@testing-library/react";

import { SearchResultControlMenuForReferral } from "./SearchResultControlMenuForReferral";

import { TestWrapper } from "TestWrapper";
import i18n from "i18n/config";

describe("SearchResultControlMenuForReferral", () => {
  const defaultProps = {
    referralFilter: "",
    referralIncludeModelIds: [],
    referralExcludeModelIds: [],
    anchorElem: null,
    handleClose: jest.fn(),
    referralFilterDispatcher: jest.fn(),
    referralIncludeModelIdsDispatcher: jest.fn(),
    referralExcludeModelIdsDispatcher: jest.fn(),
    handleSelectFilterConditions: jest.fn(),
    handleClear: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("should render menu when anchorElem is provided", () => {
    const anchorElem = document.createElement("button");
    const { container } = render(
      <SearchResultControlMenuForReferral
        {...defaultProps}
        anchorElem={anchorElem}
      />,
      { wrapper: TestWrapper },
    );

    expect(container).toBeInTheDocument();
  });

  test("should not render menu when anchorElem is null", () => {
    const { container } = render(
      <SearchResultControlMenuForReferral
        {...defaultProps}
        anchorElem={null}
      />,
      { wrapper: TestWrapper },
    );

    expect(container).toBeInTheDocument();
  });

  test("renders in English", async () => {
    await act(async () => {
      await i18n.changeLanguage("en");
    });
    const anchorElem = document.createElement("button");
    render(
      <SearchResultControlMenuForReferral
        {...defaultProps}
        anchorElem={anchorElem}
      />,
      { wrapper: TestWrapper },
    );

    expect(screen.getByText("Clear")).toBeInTheDocument();
  });
});
