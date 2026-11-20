import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";

import { CommonImportModal } from "./CommonImportModal";

import type { Mock } from "vitest";

import { TestWrapper } from "TestWrapper";
import { translate } from "i18n/config";
import { aironeApiClient } from "repository/AironeApiClient";
import { JobStatuses } from "services/Constants";

vi.mock("repository/AironeApiClient", () => ({
  aironeApiClient: {
    getImportPreview: vi.fn(),
    getJob: vi.fn(),
    importCommon: vi.fn(),
    startCommonImportPreview: vi.fn(),
  },
}));

// The form decodes the file's bytes before handing them over; jsdom has no
// File.arrayBuffer and the decoder is not what these tests are about.
const mockEncoding = vi.hoisted(() => ({
  detect: vi.fn().mockReturnValue("UTF-8"),
  convert: vi.fn().mockReturnValue("[]"),
}));
vi.mock("encoding-japanese", () => ({
  default: mockEncoding,
  ...mockEncoding,
}));

beforeEach(() => {
  File.prototype.arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(8));
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.removeItem("role-import-success");
});

const getFileInput = (): HTMLInputElement =>
  screen
    .getByTestId("upload-import-file")
    .querySelector('input[type="file"]') as HTMLInputElement;

const selectFile = (name: string) => {
  fireEvent.change(getFileInput(), {
    target: { files: [new File(["[]"], name, { type: "application/yaml" })] },
  });
};

const getImportButton = () =>
  screen.getByRole("button", { name: translate("common.import") });

describe("CommonImportModal", () => {
  const defaultProps = {
    openImportModal: true,
    closeImportModal: vi.fn(),
  };

  test("renders the title, description and caption", () => {
    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    expect(screen.getByText("データのインポート")).toBeInTheDocument();
    expect(
      screen.getByText("インポートするファイルを選択してください。"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "※モデル・アイテム・ユーザ他、いずれのインポートファイルも受け付けます。CSV形式のファイルは選択できません。",
      ),
    ).toBeInTheDocument();
  });

  test("renders nothing when openImportModal is false", () => {
    render(<CommonImportModal {...defaultProps} openImportModal={false} />, {
      wrapper: TestWrapper,
    });

    expect(screen.queryByText("データのインポート")).not.toBeInTheDocument();
  });

  test("calls closeImportModal when cancel is clicked", () => {
    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));

    expect(defaultProps.closeImportModal).toHaveBeenCalledTimes(1);
  });

  test("offers a preview button", () => {
    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    expect(
      screen.getByRole("button", { name: "変更内容を確認" }),
    ).toBeInTheDocument();
  });

  test("shows the server's reason when a preview cannot be started", async () => {
    (aironeApiClient.startCommonImportPreview as Mock).mockResolvedValue({
      jobIds: [],
      errors: ["unknown model: Foo"],
    });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    fireEvent.change(getFileInput(), {
      target: {
        files: [new File(["[]"], "import.yaml", { type: "application/yaml" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "変更内容を確認" }));

    const modal = within(getFileInput().closest<HTMLElement>("#modal")!);
    expect(await modal.findByText("unknown model: Foo")).toBeInTheDocument();
    expect(aironeApiClient.startCommonImportPreview).toHaveBeenCalledTimes(1);
    expect(aironeApiClient.importCommon).not.toHaveBeenCalled();
  });

  test("shows the server's reason when no job was started", async () => {
    (aironeApiClient.importCommon as Mock).mockResolvedValue({
      type: "entry",
      jobIds: [],
      error: ["unknown model: Foo"],
    });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    const file = new File(["[]"], "import.yaml", { type: "application/yaml" });
    fireEvent.change(getFileInput(), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    const modal = within(getFileInput().closest<HTMLElement>("#modal")!);
    expect(await modal.findByText("unknown model: Foo")).toBeInTheDocument();
    expect(aironeApiClient.importCommon).toHaveBeenCalledTimes(1);
    expect(defaultProps.closeImportModal).not.toHaveBeenCalled();
  });

  test("passes the force option when the checkbox is checked", async () => {
    (aironeApiClient.importCommon as Mock).mockResolvedValue({
      type: "entry",
      jobIds: [1],
      error: [],
    });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    fireEvent.click(screen.getByTestId("force-import"));
    fireEvent.change(getFileInput(), {
      target: {
        files: [new File(["[]"], "import.yaml", { type: "application/yaml" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "インポート" }));

    await waitFor(() =>
      expect(aironeApiClient.importCommon).toHaveBeenCalledWith(
        expect.anything(),
        true,
        undefined,
      ),
    );
  });

  test("shows each accepted job and rejection and only allows importing again after changing files", async () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const errors = ["unknown model: Foo", "permission denied: Bar"];
    vi.mocked(aironeApiClient.importCommon)
      .mockResolvedValueOnce({ type: "entry", jobIds: [17, 24], error: errors })
      .mockResolvedValueOnce({ type: "entry", jobIds: [25], error: [] });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    selectFile("import.yaml");
    fireEvent.click(getImportButton());

    const warning = within(await screen.findByRole("alert"));
    for (const error of errors) {
      expect(warning.getByText(error)).toBeInTheDocument();
    }
    expect(
      warning.getAllByRole("link").map((link) => link.getAttribute("href")),
    ).toEqual(["/ui/jobs?job_id=17", "/ui/jobs?job_id=24"]);
    expect(sessionStorage.getItem("role-import-success")).toBeNull();
    expect(reload).not.toHaveBeenCalled();

    expect(getImportButton()).toBeDisabled();
    fireEvent.click(getImportButton());
    expect(aironeApiClient.importCommon).toHaveBeenCalledTimes(1);

    selectFile("corrected.yaml");
    for (const error of errors) {
      expect(screen.queryByText(error)).not.toBeInTheDocument();
    }
    expect(getImportButton()).toBeEnabled();
    mockEncoding.convert.mockReturnValueOnce("corrected file contents");
    fireEvent.click(getImportButton());

    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(aironeApiClient.importCommon).toHaveBeenNthCalledWith(
      2,
      "corrected file contents",
      false,
      undefined,
    );
  });

  test("shows the accepted preview rows alongside model rejections without importing", async () => {
    const errors = ["unknown model: Foo", "permission denied: Bar"];
    vi.mocked(aironeApiClient.startCommonImportPreview).mockResolvedValue({
      jobIds: [42],
      errors,
    });
    (aironeApiClient.getJob as Mock).mockResolvedValue({
      status: JobStatuses.DONE,
    });
    vi.mocked(aironeApiClient.getImportPreview).mockResolvedValue({
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
          action: "create",
          changes: [],
          index: 0,
          kind: "Entry",
          name: "accepted item",
          reason: null,
          willInvokeTrigger: false,
        },
      ],
    });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    selectFile("import.yaml");
    fireEvent.click(screen.getByTestId("preview-import-file"));

    const preview = await screen.findByTestId("import-preview");
    expect(
      within(preview).getByRole("cell", { name: "accepted item" }),
    ).toBeInTheDocument();
    const warning = within(await screen.findByRole("alert"));
    for (const error of errors) {
      expect(warning.getByText(error)).toBeInTheDocument();
    }
    expect(aironeApiClient.getJob).toHaveBeenCalledWith(42);
    expect(aironeApiClient.importCommon).not.toHaveBeenCalled();
  });

  test("records success and reloads after all jobs are accepted", async () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    (aironeApiClient.importCommon as Mock).mockResolvedValue({
      type: "group",
      jobIds: [1],
      error: [],
    });

    render(<CommonImportModal {...defaultProps} />, { wrapper: TestWrapper });

    selectFile("import.yaml");
    fireEvent.click(getImportButton());

    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(sessionStorage.getItem("role-import-success")).toBe("1");
    expect(aironeApiClient.importCommon).toHaveBeenCalledTimes(1);
  });
});
