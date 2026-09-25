import AutorenewIcon from "@mui/icons-material/Autorenew";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import { Box, Typography } from "@mui/material";
import { styled } from "@mui/material/styles";
import { Link } from "react-router";
import useSWR from "swr";

import { aironeApiClient } from "repository/AironeApiClient";
import { jobsPath } from "routes/Routes";
import { JobOperations, JobStatuses } from "services/Constants";
import { jobOperationLabel } from "services/JobUtil";

const STALLED_AFTER_SECONDS = 5 * 60;
const REFRESH_INTERVAL_MS = 15 * 1000;
const MODEL_CHANGE_OPERATIONS = new Set([
  JobOperations.CREATE_ENTITY,
  JobOperations.EDIT_ENTITY,
  JobOperations.CREATE_ENTITY_V2,
  JobOperations.EDIT_ENTITY_V2,
]);
const ITEM_CHANGE_OPERATIONS = new Set([
  JobOperations.CREATE_ENTRY,
  JobOperations.EDIT_ENTRY,
  JobOperations.COPY_ENTRY,
  JobOperations.DO_COPY_ENTRY,
  JobOperations.CREATE_ENTRY_V2,
  JobOperations.EDIT_ENTRY_V2,
]);

const Notice = styled(Box)(({ theme }) => ({
  alignItems: "center",
  color: theme.palette.warning.dark,
  display: "flex",
  gap: theme.spacing(0.5),
  maxWidth: "420px",
  marginLeft: theme.spacing(2),
  minWidth: 0,
  "& a": { color: "inherit" },
}));

interface Props {
  targetId: number;
  targetKind: "model" | "item";
}

export const ChangeStatusNotice = ({ targetId, targetKind }: Props) => {
  const { data, error } = useSWR(
    ["change-status-jobs", targetId],
    () => aironeApiClient.getJobs(1, targetId),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );

  const operations =
    targetKind === "model" ? MODEL_CHANGE_OPERATIONS : ITEM_CHANGE_OPERATIONS;
  const jobs = (data?.results ?? []).filter((job) =>
    operations.has(job.operation ?? 0),
  );
  const activeJob = jobs.find(
    (job) =>
      job.status === JobStatuses.PREPARING ||
      job.status === JobStatuses.PROCESSING,
  );
  const latestJob = jobs[0];
  const failedJob =
    latestJob &&
    [
      JobStatuses.ERROR,
      JobStatuses.TIMEOUT,
      JobStatuses.CANCELED,
      JobStatuses.WARNING,
    ].includes(latestJob.status ?? 0);
  const reportedActiveJob = error ? undefined : activeJob;

  const subject = targetKind === "model" ? "モデル" : "アイテム";
  const affected = targetKind === "model" ? "属性や設定" : "値や検索結果";
  const isChecking = data === undefined && !error;
  let message = `${subject}の変更状況を確認できません。${affected}が更新前の可能性があります。`;
  if (isChecking) {
    message = `${subject}の変更状況を確認しています。${affected}が更新前の可能性があります。`;
  } else if (reportedActiveJob) {
    const operation = jobOperationLabel(reportedActiveJob.operation);
    message =
      (reportedActiveJob.passedTime ?? 0) >= STALLED_AFTER_SECONDS
        ? `${subject}の${operation}に時間がかかっています。${affected}が更新前の可能性があります。`
        : `${subject}の${operation}を反映中です。${affected}が更新前の可能性があります。`;
  } else if (failedJob && !error) {
    message = `${subject}の変更が完了していません。${affected}が更新前の可能性があります。`;
  }

  return (
    <Notice role="status" aria-live="polite">
      {reportedActiveJob || isChecking ? (
        <AutorenewIcon fontSize="small" />
      ) : (
        <ErrorOutlineIcon fontSize="small" />
      )}
      <Typography variant="body2" component={Link} to={jobsPath(targetId)}>
        {message}
      </Typography>
    </Notice>
  );
};
