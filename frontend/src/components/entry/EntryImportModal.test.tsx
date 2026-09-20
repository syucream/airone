import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { EntryImportModal } from "./EntryImportModal";

import { TestWrapper } from "TestWrapper";

const mocks = vi.hoisted(() => ({
  importEntries: vi.fn(),
  startImportEntriesPreview: vi.fn(),
  waitForImportPreviews: vi.fn(),
}));

vi.mock("encoding-japanese", () => ({
  default: {
    detect: vi.fn().mockReturnValue("UTF-8"),
    convert: vi.fn().mockReturnValue("imported entries"),
  },
}));

vi.mock("repository/AironeApiClient", () => ({
  aironeApiClient: {
    importEntries: mocks.importEntries,
    startImportEntriesPreview: mocks.startImportEntriesPreview,
  },
}));

vi.mock("services/ImportPreviewJob", () => ({
  ImportPreviewFailure: class ImportPreviewFailure extends Error {},
  waitForImportPreviews: mocks.waitForImportPreviews,
}));

const preview = {
  summary: {
    created: 1,
    updated: 0,
    unchanged: 0,
    skipped: 0,
    errored: 0,
    total: 1,
  },
  count: 1,
  truncated: false,
  rows: [
    {
      index: 0,
      kind: "Entry",
      name: "approved entry",
      action: "create" as const,
      reason: null,
      changes: [],
    },
  ],
};

const selectFile = () => {
  const input = document.querySelector('input[type="file"]');
  if (input == null) {
    throw new Error("file input is not rendered");
  }
  fireEvent.change(input, {
    target: {
      files: [
        new File(["entries"], "entries.yaml", { type: "application/yaml" }),
      ],
    },
  });
};

describe("EntryImportModal", () => {
  const props = {
    openImportModal: true,
    closeImportModal: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.importEntries.mockImplementation(() => new Promise<void>(() => {}));
    mocks.startImportEntriesPreview.mockResolvedValue({
      jobIds: [101, 202],
      errors: [],
    });
    mocks.waitForImportPreviews.mockResolvedValue(preview);
  });

  test("starts every entry preview job and imports with all approved job ids", async () => {
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByTestId("preview-import-file"));

    await waitFor(() =>
      expect(mocks.startImportEntriesPreview).toHaveBeenCalledWith(
        "imported entries",
      ),
    );
    expect(mocks.waitForImportPreviews).toHaveBeenCalledWith(
      [101, 202],
      expect.anything(),
    );
    await screen.findByTestId("import-preview");

    fireEvent.click(screen.getByRole("checkbox", { name: "強制インポート" }));
    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    await waitFor(() =>
      expect(mocks.importEntries).toHaveBeenCalledWith(
        "imported entries",
        true,
        [101, 202],
      ),
    );
  });

  test("imports without preview or an approval id when the user skips preview", async () => {
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    await waitFor(() =>
      expect(mocks.importEntries).toHaveBeenCalledWith(
        "imported entries",
        false,
        [],
      ),
    );
    expect(mocks.startImportEntriesPreview).not.toHaveBeenCalled();
  });

  test("shows backend preview errors when no model in the file can be previewed", async () => {
    mocks.startImportEntriesPreview.mockResolvedValue({
      jobIds: [],
      errors: ["private: Entity is permission denied."],
    });
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByTestId("preview-import-file"));

    expect(
      await screen.findByText("private: Entity is permission denied."),
    ).toBeInTheDocument();
    expect(mocks.waitForImportPreviews).not.toHaveBeenCalled();
  });

  test("blocks approval when only some models can be previewed", async () => {
    mocks.startImportEntriesPreview.mockResolvedValue({
      jobIds: [101],
      errors: ["private: Entity is permission denied."],
    });
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByTestId("preview-import-file"));

    expect(
      await screen.findByText("private: Entity is permission denied."),
    ).toBeInTheDocument();
    expect(mocks.waitForImportPreviews).not.toHaveBeenCalled();
    expect(mocks.importEntries).not.toHaveBeenCalled();
  });

  test("shows a preview request failure instead of starting an unapproved import", async () => {
    mocks.startImportEntriesPreview.mockRejectedValue(
      new Error("request failed"),
    );
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByTestId("preview-import-file"));

    expect(
      await screen.findByText("変更内容の確認に失敗しました"),
    ).toBeInTheDocument();
    expect(mocks.waitForImportPreviews).not.toHaveBeenCalled();
  });

  test("shows an import error and does not silently report success", async () => {
    mocks.importEntries.mockRejectedValue(new Error("request failed"));
    render(<EntryImportModal {...props} />, { wrapper: TestWrapper });
    selectFile();

    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    expect(
      await screen.findByText("ファイルのアップロードに失敗しました"),
    ).toBeInTheDocument();
  });
});
