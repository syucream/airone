import { JobSerializers } from "@dmm-com/airone-apiclient-typescript-fetch";
import { render, screen, waitFor } from "@testing-library/react";
import { useSWRConfig } from "swr";

import { ChangeStatusNotice } from "./ChangeStatusNotice";

import { TestWrapper } from "TestWrapper";
import { aironeApiClient } from "repository/AironeApiClient";
import { JobOperations, JobStatuses } from "services/Constants";

const makeJob = (status: number, passedTime = 1): JobSerializers => ({
  id: 5,
  user: "alice",
  text: "",
  status,
  operation: JobOperations.EDIT_ENTRY,
  createdAt: new Date(),
  target: { id: 42, name: "item", schemaId: 2, schemaName: "model" },
  passedTime,
});

const RefreshJobs = () => {
  const { mutate } = useSWRConfig();
  return (
    <button onClick={() => mutate(["change-status-jobs", 42])}>更新</button>
  );
};

afterEach(() => vi.restoreAllMocks());

test("shows a checking state before job history is available", () => {
  vi.spyOn(aironeApiClient, "getJobs").mockImplementation(
    () => new Promise(() => {}),
  );

  render(<ChangeStatusNotice targetId={42} targetKind="model" />, {
    wrapper: TestWrapper,
  });

  expect(screen.getByText(/モデルの変更状況を確認しています/)).toBeVisible();
});

test("shows the affected data and operation while a change is running", async () => {
  vi.spyOn(aironeApiClient, "getJobs").mockResolvedValue({
    count: 1,
    results: [makeJob(JobStatuses.PROCESSING)],
  });

  render(<ChangeStatusNotice targetId={42} targetKind="item" />, {
    wrapper: TestWrapper,
  });

  expect(
    await screen.findByText(/アイテムの編集を反映中です。値や検索結果/),
  ).toHaveAttribute("href", "/ui/jobs?target_id=42");
});

test("calls out a long running change without claiming it has finished", async () => {
  vi.spyOn(aironeApiClient, "getJobs").mockResolvedValue({
    count: 1,
    results: [makeJob(JobStatuses.PROCESSING, 301)],
  });

  render(<ChangeStatusNotice targetId={42} targetKind="item" />, {
    wrapper: TestWrapper,
  });

  expect(await screen.findByText(/編集に時間がかかっています/)).toBeVisible();
});

test("updates the notice when the job fails while the page stays open", async () => {
  const getJobs = vi.spyOn(aironeApiClient, "getJobs");
  getJobs.mockResolvedValueOnce({
    count: 1,
    results: [makeJob(JobStatuses.PROCESSING)],
  });
  getJobs.mockResolvedValue({
    count: 1,
    results: [makeJob(JobStatuses.ERROR)],
  });

  render(
    <>
      <ChangeStatusNotice targetId={42} targetKind="item" />
      <RefreshJobs />
    </>,
    { wrapper: TestWrapper },
  );

  await screen.findByText(/編集を反映中です/);
  screen.getByRole("button", { name: "更新" }).click();
  await waitFor(() =>
    expect(screen.getByText(/変更が完了していません/)).toBeVisible(),
  );
});

test("does not assume another user's invisible job has finished", async () => {
  vi.spyOn(aironeApiClient, "getJobs").mockResolvedValue({
    count: 0,
    results: [],
  });

  render(<ChangeStatusNotice targetId={42} targetKind="model" />, {
    wrapper: TestWrapper,
  });

  expect(
    await screen.findByText(/モデルの変更状況を確認できません。属性や設定/),
  ).toBeVisible();
});

test("reports an unknown state when the job request fails", async () => {
  vi.spyOn(aironeApiClient, "getJobs").mockRejectedValue(
    new Error("network unavailable"),
  );

  render(<ChangeStatusNotice targetId={42} targetKind="item" />, {
    wrapper: TestWrapper,
  });

  expect(
    await screen.findByText(/アイテムの変更状況を確認できません/),
  ).toBeVisible();
});

test("does not describe an unrelated export failure as a failed item change", async () => {
  vi.spyOn(aironeApiClient, "getJobs").mockResolvedValue({
    count: 1,
    results: [
      {
        ...makeJob(JobStatuses.ERROR),
        operation: JobOperations.EXPORT_ENTRY,
      },
    ],
  });

  render(<ChangeStatusNotice targetId={42} targetKind="item" />, {
    wrapper: TestWrapper,
  });

  expect(
    await screen.findByText(/アイテムの変更状況を確認できません/),
  ).toBeVisible();
});
