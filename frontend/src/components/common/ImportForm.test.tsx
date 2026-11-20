/**
 */

import { ThemeProvider, createTheme } from "@mui/material/styles";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { SnackbarProvider } from "notistack";
import { FC, ReactNode } from "react";
import { MemoryRouter } from "react-router";

import { ImportForm } from "./ImportForm";

import i18n from "i18n/config";
import { JobStatuses } from "services/Constants";

// Ensure File is available in the global scope before tests run
if (typeof global.File === "undefined") {
  class MockFile implements Partial<File> {
    readonly name: string;
    readonly size: number;
    readonly type: string;

    constructor(
      chunks: BlobPart[],
      filename: string,
      options?: FilePropertyBag,
    ) {
      this.name = filename;
      this.size = chunks.length > 0 ? 100 : 0;
      this.type = options?.type || "";
    }

    arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(8));
  }

  global.File = MockFile as unknown as typeof File;
}

// Mock encoding-japanese
const mockEncoding = vi.hoisted(() => ({
  detect: vi.fn().mockReturnValue("UTF-8"),
  convert: vi.fn().mockReturnValue("Entity: []"),
}));
vi.mock("encoding-japanese", () => ({
  default: mockEncoding,
  ...mockEncoding,
}));

const mockCancelJob = vi.fn().mockResolvedValue(undefined);
const mockDownloadImportPreview = vi.fn().mockResolvedValue(undefined);
const mockGetJob = vi.fn();
const mockGetImportPreview = vi.fn();
vi.mock("repository/AironeApiClient", () => ({
  aironeApiClient: {
    getJob: (...args: unknown[]) => mockGetJob(...args),
    getImportPreview: (...args: unknown[]) => mockGetImportPreview(...args),
    cancelJob: (...args: unknown[]) => mockCancelJob(...args),
    downloadImportPreview: (...args: unknown[]) =>
      mockDownloadImportPreview(...args),
  },
}));

// Mock react-router
const mockNavigate = vi.fn();
vi.mock("react-router", async () => ({
  ...((await vi.importActual("react-router")) as object),
  useNavigate: () => mockNavigate,
}));

// MUI's Input puts data-testid on its wrapper, so the actual <input> has to be
// looked up to make React see the change event.
const selectFile = (file: File) => {
  const input = document.querySelector('input[type="file"]');
  if (input == null) {
    throw new Error("file input is not rendered");
  }
  fireEvent.change(input, { target: { files: [file] } });
};

const TestWrapper: FC<{ children: ReactNode }> = ({ children }) => {
  const theme = createTheme();
  return (
    <ThemeProvider theme={theme}>
      <SnackbarProvider maxSnack={1}>
        <MemoryRouter>{children}</MemoryRouter>
      </SnackbarProvider>
    </ThemeProvider>
  );
};

const previewWith = (
  rows: { index: number; name: string; action: string }[],
) => ({
  summary: {
    created: rows.filter((x) => x.action === "create").length,
    updated: 0,
    unchanged: 0,
    skipped: 0,
    errored: rows.filter((x) => x.action === "error").length,
    total: rows.length,
  },
  count: rows.length,
  truncated: false,
  rows: rows.map((row) => ({
    ...row,
    kind: "Entity",
    reason: null,
    changes: [],
    willInvokeTrigger: false,
  })),
});

describe("ImportForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetJob.mockReset().mockResolvedValue({ status: JobStatuses.DONE });
    mockGetImportPreview.mockReset();
    // The real client returns promises; a bare vi.fn() would not, and the code
    // chains onto what it gets back.
    mockCancelJob.mockResolvedValue(undefined);
    mockDownloadImportPreview.mockResolvedValue(undefined);
    // Ensure File.prototype.arrayBuffer is mocked for encoding detection
    if (global.File && global.File.prototype) {
      global.File.prototype.arrayBuffer = vi
        .fn()
        .mockResolvedValue(new ArrayBuffer(8));
    }
  });

  test("should render all UI elements", () => {
    const handleImport = vi.fn();

    render(<ImportForm handleImport={handleImport} />, {
      wrapper: TestWrapper,
    });

    expect(screen.getByTestId("upload-import-file")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "インポート" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "キャンセル" }),
    ).toBeInTheDocument();
  });

  test("should handle file selection", () => {
    const handleImport = vi.fn();
    const file = new File(["test content"], "test.yaml", {
      type: "application/yaml",
    });

    render(<ImportForm handleImport={handleImport} />, {
      wrapper: TestWrapper,
    });

    const fileInput = screen.getByTestId("upload-import-file");
    fireEvent.change(fileInput, { target: { files: [file] } });

    expect((fileInput as HTMLInputElement).files).toHaveLength(1);
    expect((fileInput as HTMLInputElement).files![0]).toBe(file);
  });

  test("should not offer a preview when the caller does not support it", () => {
    render(<ImportForm handleImport={vi.fn()} />, { wrapper: TestWrapper });

    expect(screen.queryByTestId("preview-import-file")).not.toBeInTheDocument();
  });

  test("should show what the file would change before importing it", async () => {
    mockGetImportPreview.mockResolvedValueOnce({
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
          kind: "Entity",
          name: "entity1",
          action: "create",
          reason: null,
          changes: [{ field: "note", before: null, after: "a note" }],
        },
      ],
    });
    const handlePreview = vi.fn().mockResolvedValue([42]);

    render(
      <ImportForm handleImport={vi.fn()} handlePreview={handlePreview} />,
      { wrapper: TestWrapper },
    );

    selectFile(
      new File(["Entity: []"], "entity.yaml", { type: "application/yaml" }),
    );
    fireEvent.click(screen.getByTestId("preview-import-file"));

    await waitFor(() =>
      expect(screen.getByTestId("import-preview")).toBeInTheDocument(),
    );
    expect(handlePreview).toHaveBeenCalledTimes(1);
    // The form starts the jobs and then waits for them; it never previews inline.
    expect(mockGetJob).toHaveBeenCalledWith(42);
    expect(screen.getByText("新規作成 1")).toBeInTheDocument();
    expect(screen.getByText("entity1")).toBeInTheDocument();
    expect(screen.getByText("note: a note")).toBeInTheDocument();
  });

  test("restarts every job when filtering and retries a failed page from the same offsets", async () => {
    const previews = [
      previewWith([
        { index: 0, name: "created", action: "create" },
        { index: 1, name: "error-a", action: "error" },
      ]),
      previewWith([
        { index: 0, name: "error-b", action: "error" },
        { index: 1, name: "error-c", action: "error" },
        { index: 2, name: "error-d", action: "error" },
      ]),
    ];
    mockGetImportPreview.mockImplementation(
      (jobId: number, { action, offset = 0 }) => {
        const preview = previews[jobId];
        const rows = preview.rows.filter(
          (row) => !action || row.action === action,
        );
        return {
          ...preview,
          count: rows.length,
          rows: rows.slice(offset, offset + 2),
        };
      },
    );
    const handlePreview = vi.fn().mockResolvedValue([0, 1]);
    render(
      <ImportForm handleImport={vi.fn()} handlePreview={handlePreview} />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["items"], "items.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));
    await screen.findByText("created");

    const toggleErrors = () =>
      fireEvent.click(screen.getByTestId("import-preview-filter-error"));
    await act(async () => toggleErrors());
    for (const jobId of [0, 1]) {
      expect(mockGetImportPreview).toHaveBeenCalledWith(
        jobId,
        expect.objectContaining({ action: "error", offset: 0 }),
      );
    }
    expect(screen.queryByText("created")).not.toBeInTheDocument();
    expect(screen.getByText("error-a")).toBeInTheDocument();
    const more = screen.getByTestId("import-preview-load-more");
    expect(more).toHaveTextContent("1");

    mockGetImportPreview
      .mockClear()
      .mockRejectedValueOnce(new Error("page unavailable"));
    await act(async () => fireEvent.click(more));
    expect(screen.queryByText("error-d")).not.toBeInTheDocument();
    await act(async () => fireEvent.click(more));
    expect(mockGetImportPreview).toHaveBeenCalledTimes(2);
    for (const call of mockGetImportPreview.mock.calls) {
      expect(call).toEqual([
        1,
        expect.objectContaining({ action: "error", offset: 2 }),
      ]);
    }
    expect(screen.getByText("error-d")).toBeInTheDocument();
    expect(
      screen.queryByTestId("import-preview-load-more"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("合計 5")).toBeInTheDocument();

    await act(async () => toggleErrors());
    expect(screen.getByText("created")).toBeInTheDocument();
    expect(screen.queryByText("error-d")).not.toBeInTheDocument();
    expect(screen.getByTestId("import-preview-load-more")).toHaveTextContent(
      "1",
    );
    expect(handlePreview).toHaveBeenCalledTimes(1);
  });

  test("should append the next page instead of replacing what is shown", async () => {
    mockGetImportPreview.mockResolvedValueOnce({
      ...previewWith([{ index: 0, name: "first", action: "create" }]),
      count: 2,
    });
    mockGetImportPreview.mockResolvedValueOnce({
      ...previewWith([{ index: 1, name: "second", action: "create" }]),
      count: 2,
    });

    render(
      <ImportForm
        handleImport={vi.fn()}
        handlePreview={vi.fn().mockResolvedValue([7])}
      />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["Entity: []"], "entity.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));
    await waitFor(() =>
      expect(screen.getByTestId("import-preview")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("import-preview-load-more"));

    await waitFor(() => expect(screen.getByText("second")).toBeInTheDocument());
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(mockGetImportPreview).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ offset: 1 }),
    );
  });

  test("appends every row when the two jobs return different page sizes", async () => {
    const pageSizes = [3, 2];
    const jobs = [5, 3].map((size, jobId) =>
      previewWith(
        Array.from({ length: size }, (_, index) => ({
          index,
          name: `job-${jobId}-${index}`,
          action: "create",
        })),
      ),
    );
    mockGetImportPreview.mockImplementation((jobId: number, { offset = 0 }) => {
      const job = jobs[jobId];
      return {
        ...job,
        rows: job.rows.slice(offset, offset + pageSizes[jobId]),
      };
    });
    render(
      <ImportForm
        handleImport={vi.fn()}
        handlePreview={vi.fn().mockResolvedValue([0, 1])}
      />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["items"], "items.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));

    const more = await screen.findByTestId("import-preview-load-more");
    expect(more).toHaveTextContent("3");
    await act(async () => fireEvent.click(more));

    expect(mockGetImportPreview).toHaveBeenCalledWith(
      0,
      expect.objectContaining({ offset: pageSizes[0] }),
    );
    expect(mockGetImportPreview).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ offset: pageSizes[1] }),
    );
    const names = Array.from(
      document.querySelectorAll<HTMLTableRowElement>("tbody tr"),
      (row) => row.cells[2].textContent,
    );
    expect(names.sort()).toEqual(
      jobs.flatMap((job) => job.rows.map((row) => row.name)).sort(),
    );
    expect(
      screen.queryByTestId("import-preview-load-more"),
    ).not.toBeInTheDocument();
  });

  test("should let the user give up on a preview that is still running", async () => {
    // Previewing a large file takes as long as importing it, so the wait has to
    // be escapable -- which is why previews run as cancelable jobs.
    mockGetJob.mockReturnValue(new Promise(() => {}));

    render(
      <ImportForm
        handleImport={vi.fn()}
        handlePreview={vi.fn().mockResolvedValue([7, 8])}
      />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["Entity: []"], "entity.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));

    await waitFor(() =>
      expect(screen.getByTestId("cancel-import-preview")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId("cancel-import-preview"));

    await waitFor(() => expect(mockCancelJob).toHaveBeenCalledWith(7));
    expect(mockCancelJob).toHaveBeenCalledWith(8);
  });

  test("should hand the approved preview to the import", async () => {
    const handleImport = vi.fn().mockResolvedValue(undefined);
    mockGetImportPreview.mockResolvedValueOnce(
      previewWith([{ index: 0, name: "ok", action: "create" }]),
    );

    render(
      <ImportForm
        handleImport={handleImport}
        handlePreview={vi.fn().mockResolvedValue([7])}
      />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["Entity: []"], "entity.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));
    await waitFor(() =>
      expect(screen.getByTestId("import-preview")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    // The import needs to know which preview was approved, so that it can leave
    // alone anything changed since.
    await waitFor(() =>
      expect(handleImport).toHaveBeenCalledWith(expect.anything(), [7]),
    );
  });

  test("should let the user download the whole preview", async () => {
    mockGetImportPreview.mockResolvedValueOnce(
      previewWith([{ index: 0, name: "ok", action: "create" }]),
    );

    render(
      <ImportForm
        handleImport={vi.fn()}
        handlePreview={vi.fn().mockResolvedValue([7])}
      />,
      { wrapper: TestWrapper },
    );
    selectFile(new File(["Entity: []"], "entity.yaml"));
    fireEvent.click(screen.getByTestId("preview-import-file"));
    await waitFor(() =>
      expect(screen.getByTestId("import-preview")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("import-preview-download"));

    await waitFor(() =>
      expect(mockDownloadImportPreview).toHaveBeenCalledWith(
        7,
        "import_preview.csv",
      ),
    );
  });

  test("should let the user import without previewing", async () => {
    const handleImport = vi.fn().mockResolvedValue(undefined);
    const handlePreview = vi.fn();

    render(
      <ImportForm handleImport={handleImport} handlePreview={handlePreview} />,
      { wrapper: TestWrapper },
    );

    selectFile(
      new File(["Entity: []"], "entity.yaml", { type: "application/yaml" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    await waitFor(() => expect(handleImport).toHaveBeenCalledTimes(1));
    expect(handlePreview).not.toHaveBeenCalled();
  });

  test("should not attempt import when no file is selected", () => {
    const handleImport = vi.fn();

    render(<ImportForm handleImport={handleImport} />, {
      wrapper: TestWrapper,
    });

    const importButton = screen.getByRole("button", { name: "インポート" });
    fireEvent.click(importButton);

    expect(handleImport).not.toHaveBeenCalled();
  });

  describe("English", () => {
    afterEach(async () => {
      await i18n.changeLanguage("ja");
    });

    test("should render buttons in English", async () => {
      await act(async () => {
        await i18n.changeLanguage("en");
      });

      const handleImport = vi.fn();

      render(<ImportForm handleImport={handleImport} />, {
        wrapper: TestWrapper,
      });

      expect(
        screen.getByRole("button", { name: "Import" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Cancel" }),
      ).toBeInTheDocument();
    });
  });
});
