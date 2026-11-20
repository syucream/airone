import {
  ImportPreview,
  ImportPreviewAction,
} from "components/common/ImportPreview";
import { translate } from "i18n/config";
import { aironeApiClient } from "repository/AironeApiClient";
import { ImportPreviewParam, JobStatuses } from "services/Constants";

export class ImportPreviewFailure extends Error {}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const statusMessage = (status: number): string | undefined => {
  switch (status) {
    case JobStatuses.ERROR:
      return translate("importPreview.job.confirmFailed");
    case JobStatuses.TIMEOUT:
      return translate("importPreview.job.confirmTimedOut");
    case JobStatuses.CANCELED:
      return translate("importPreview.job.confirmCancelled");
    default:
      return undefined;
  }
};

interface ImportPreviewPage {
  action?: ImportPreviewAction[];
  offset?: number;
  limit?: number;
}

interface JobCursor {
  jobId: number;
  offset: number;
}

export interface PagedImportPreview extends ImportPreview {
  nextPage: JobCursor[];
}

const mergePreviews = (
  jobs: (JobCursor & { preview: ImportPreview })[],
): PagedImportPreview => ({
  nextPage: jobs.flatMap(({ jobId, offset, preview }) => {
    const nextOffset = offset + preview.rows.length;
    return nextOffset < preview.count ? [{ jobId, offset: nextOffset }] : [];
  }),
  summary: jobs.reduce(
    (merged, { preview }) => ({
      created: merged.created + preview.summary.created,
      updated: merged.updated + preview.summary.updated,
      unchanged: merged.unchanged + preview.summary.unchanged,
      skipped: merged.skipped + preview.summary.skipped,
      errored: merged.errored + preview.summary.errored,
      total: merged.total + preview.summary.total,
    }),
    {
      created: 0,
      updated: 0,
      unchanged: 0,
      skipped: 0,
      errored: 0,
      total: 0,
    },
  ),
  rows: jobs.flatMap(({ jobId, preview }) =>
    preview.rows.map((row) => ({ ...row, jobId })),
  ),
  count: jobs.reduce((total, { preview }) => total + preview.count, 0),
  truncated: jobs.some(({ preview }) => preview.truncated),
});

/**
 * Wait for every preview job of one file, then report them as one preview.
 *
 * An item import file may cover several models, and the backend previews each
 * of them on its own job -- but the user chose one file and expects one answer.
 */
export const waitForImportPreviews = async (
  jobIds: number[],
  options: {
    onProgress?: (text: string) => void;
    isAbandoned?: () => boolean;
    page?: ImportPreviewPage;
  } = {},
): Promise<PagedImportPreview> =>
  mergePreviews(
    await Promise.all(
      jobIds.map(async (jobId) => ({
        jobId,
        offset: options.page?.offset ?? 0,
        preview: await waitForImportPreview(jobId, options),
      })),
    ),
  );

export const fetchImportPreviewPage = async (
  cursors: JobCursor[],
  action: ImportPreviewAction[],
): Promise<PagedImportPreview> =>
  mergePreviews(
    await Promise.all(
      cursors.map(async ({ jobId, offset }) => ({
        jobId,
        offset,
        preview: await aironeApiClient.getImportPreview(
          jobId,
          toQuery({ action, offset }),
        ),
      })),
    ),
  );

const toQuery = (page: ImportPreviewPage) => ({
  offset: page.offset,
  limit: page.limit,
  action: page.action?.join(","),
});

/**
 * Wait for a preview job to finish, then read its result.
 *
 * Building a preview costs as much as the import it previews, so the backend
 * runs it on a worker. `onProgress` receives the job's own progress text, which
 * is the only thing that tells the user a large file is still being read.
 */
export const waitForImportPreview = async (
  jobId: number,
  options: {
    onProgress?: (text: string) => void;
    isAbandoned?: () => boolean;
    page?: ImportPreviewPage;
  } = {},
): Promise<ImportPreview> => {
  const { onProgress, isAbandoned } = options;
  for (;;) {
    if (isAbandoned?.()) {
      throw new ImportPreviewFailure(
        translate("importPreview.job.confirmCancelled"),
      );
    }

    const job = await aironeApiClient.getJob(jobId);
    if (job.status === JobStatuses.DONE) {
      return aironeApiClient.getImportPreview(
        jobId,
        toQuery(options.page ?? {}),
      );
    }
    const message = job.status != null ? statusMessage(job.status) : undefined;
    if (message != null) {
      throw new ImportPreviewFailure(message);
    }

    onProgress?.(job.text ?? "");
    await sleep(ImportPreviewParam.POLL_INTERVAL_MS);
  }
};
