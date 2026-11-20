import {
  Box,
  Button,
  CircularProgress,
  Input,
  Typography,
} from "@mui/material";
import Encoding from "encoding-japanese";
import { useSnackbar } from "notistack";
import { ChangeEvent, FC, useEffect, useRef, useState } from "react";

import { useTranslation } from "../../hooks/useTranslation";
import {
  isResponseError,
  toReportableNonFieldErrors,
} from "../../services/AironeAPIErrorUtil";

import { ImportPreviewAction } from "./ImportPreview";
import { ImportPreviewResult } from "./ImportPreviewResult";

import { aironeApiClient } from "repository/AironeApiClient";
import {
  ImportPreviewFailure,
  PagedImportPreview,
  fetchImportPreviewPage,
  waitForImportPreviews,
} from "services/ImportPreviewJob";

interface Props {
  /** Receives the preview the user approved, when they previewed at all. */
  handleImport: (
    data: string | ArrayBuffer,
    previewJobIds: number[],
  ) => Promise<void>;
  handleCancel?: () => void;
  /**
   * When given, the user can review what the file would change before importing
   * it. The callback starts the preview jobs and returns their ids; this form
   * waits for all of them. Previewing stays optional -- importing directly is
   * always one click away, for users in a hurry or files not worth the wait.
   */
  handlePreview?: (data: string | ArrayBuffer) => Promise<number[]>;
}

// The file is read once and decoded in place. Reading it again through a
// FileReader would only repeat work the ArrayBuffer already gave us.
const readFileAsText = async (file: File): Promise<string> => {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const detected = Encoding.detect(bytes);

  return Encoding.convert(bytes, {
    to: "UNICODE",
    from: typeof detected === "string" ? detected : "AUTO",
    type: "string",
  });
};

export const ImportForm: FC<Props> = ({
  handleImport,
  handleCancel,
  handlePreview,
}) => {
  const { t } = useTranslation();
  const [file, setFile] = useState<File>();
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [preview, setPreview] = useState<PagedImportPreview>();
  // A ref, not state: the cancel button is on screen before the jobs have been
  // started, and it has to reach the ids the moment they exist.
  const previewJobIds = useRef<number[]>([]);
  const [actions, setActions] = useState<ImportPreviewAction[]>([]);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState<string>();
  const abandoned = useRef(false);
  const { enqueueSnackbar } = useSnackbar();

  // Leaving the form (closing the dialog) has to stop the polling loop, or it
  // would keep asking about a job nobody is waiting for any more. The flag is
  // cleared on mount as well, since StrictMode runs the cleanup once before the
  // real mount and would otherwise leave the form permanently abandoned.
  useEffect(() => {
    abandoned.current = false;
    return () => {
      abandoned.current = true;
    };
  }, []);

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    event.target.files && setFile(event.target.files[0]);
    setPreview(undefined);
    previewJobIds.current = [];
    setActions([]);
    setErrorMessage("");
  };

  const reportError = async (e: unknown, fallback: string) => {
    if (e instanceof ImportPreviewFailure) {
      setErrorMessage(e.message);
      enqueueSnackbar(e.message, { variant: "error" });
      return;
    }
    if (e instanceof Error && isResponseError(e)) {
      if (e.response.status === 403) {
        setErrorMessage(t("importForm.permissionDenied"));
        enqueueSnackbar(t("importForm.permissionDenied"), {
          variant: "error",
        });
        return;
      }
      const reportableError = await toReportableNonFieldErrors(e);
      const message = `${fallback}: ${reportableError ?? ""}`;
      setErrorMessage(message);
      enqueueSnackbar(message, { variant: "error" });
      return;
    }
    setErrorMessage(fallback);
    enqueueSnackbar(fallback, { variant: "error" });
  };

  const onPreview = async () => {
    if (!file || handlePreview == null) {
      return;
    }

    setProcessing(true);
    setProgress(t("importForm.checkingChanges"));
    try {
      const jobIds = await handlePreview(await readFileAsText(file));
      previewJobIds.current = jobIds;
      setPreview(
        await waitForImportPreviews(jobIds, {
          onProgress: setProgress,
          isAbandoned: () => abandoned.current,
        }),
      );
      setErrorMessage("");
    } catch (e) {
      setPreview(undefined);
      await reportError(e, t("importForm.previewFailed"));
    } finally {
      setProcessing(false);
      setProgress(undefined);
    }
  };

  // Filtering and paging re-read the finished jobs; the file is never sent again.
  const readPage = async (filter?: ImportPreviewAction[]) => {
    if (preview == null) return;
    setProcessing(true);
    try {
      const cursors =
        filter == null
          ? preview.nextPage
          : previewJobIds.current.map((jobId) => ({ jobId, offset: 0 }));
      const page = await fetchImportPreviewPage(cursors, filter ?? actions);
      if (filter == null) {
        setPreview({
          ...preview,
          rows: [...preview.rows, ...page.rows],
          nextPage: page.nextPage,
        });
      } else {
        setPreview(page);
        setActions(filter);
      }
      setErrorMessage("");
    } catch (e) {
      await reportError(e, t("importForm.loadPageFailed"));
    } finally {
      setProcessing(false);
    }
  };

  const onDownloadPreview = async () => {
    try {
      await Promise.all(
        previewJobIds.current.map((jobId) =>
          aironeApiClient.downloadImportPreview(
            jobId,
            previewJobIds.current.length > 1
              ? `import_preview_${jobId}.csv`
              : "import_preview.csv",
          ),
        ),
      );
    } catch (e) {
      await reportError(e, t("importForm.downloadPreviewFailed"));
    }
  };

  // Previewing a large file takes as long as importing it, so it has to be
  // possible to give up on one -- which is why previews run as cancelable jobs.
  // The polling loop notices the cancellation and reports it; a job that has
  // just finished refuses to be cancelled, which is not worth telling anyone.
  const onCancelPreview = async () => {
    await Promise.all(
      previewJobIds.current.map((jobId) =>
        aironeApiClient.cancelJob(jobId).catch(() => undefined),
      ),
    );
  };

  const onImport = async () => {
    if (!file) {
      return;
    }

    setProcessing(true);
    try {
      await handleImport(await readFileAsText(file), previewJobIds.current);
      sessionStorage.setItem("role-import-success", "1");
      window.location.reload();
    } catch (e) {
      await reportError(e, t("notification.uploadFailed"));
    } finally {
      setProcessing(false);
    }
  };

  return (
    <Box display="flex" flexDirection="column">
      <Input
        type="file"
        disabled={processing}
        onChange={onChange}
        data-testid="upload-import-file"
      />

      {processing && progress != null && (
        <Box display="flex" alignItems="center" gap="8px" my="12px">
          <CircularProgress size={16} />
          <Typography variant="body2">{progress}</Typography>
          <Button
            size="small"
            color="info"
            onClick={onCancelPreview}
            data-testid="cancel-import-preview"
          >
            {t("importForm.cancelPreview")}
          </Button>
        </Box>
      )}

      {preview && (
        <ImportPreviewResult
          preview={preview}
          actions={actions}
          onChangeActions={readPage}
          onLoadMore={() => readPage()}
          onDownload={onDownloadPreview}
          loading={processing}
        />
      )}

      <Typography color="error" variant="caption" my="4px">
        {errorMessage}
      </Typography>
      <Box display="flex" justifyContent="flex-end">
        {handlePreview != null && preview == null && (
          <Button
            variant="outlined"
            color="secondary"
            disabled={!file || processing}
            onClick={onPreview}
            sx={{ m: "4px" }}
            data-testid="preview-import-file"
          >
            {t("importForm.previewButton")}
          </Button>
        )}
        <Button
          type="submit"
          variant="contained"
          color="secondary"
          disabled={processing}
          onClick={onImport}
          sx={{ m: "4px" }}
        >
          {t("common.import")}
        </Button>
        <Button
          variant="contained"
          color="info"
          onClick={handleCancel}
          sx={{ m: "4px" }}
        >
          {t("common.cancel")}
        </Button>
      </Box>
    </Box>
  );
};
