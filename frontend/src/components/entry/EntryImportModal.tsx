import { Box, Checkbox, Typography } from "@mui/material";
import { FC, useCallback, useState } from "react";

import { AironeModal } from "../common/AironeModal";

import { ImportForm } from "components/common/ImportForm";
import { aironeApiClient } from "repository/AironeApiClient";
import { ImportPreviewFailure } from "services/ImportPreviewJob";

interface Props {
  openImportModal: boolean;
  closeImportModal: () => void;
}

export const EntryImportModal: FC<Props> = ({
  openImportModal,
  closeImportModal,
}) => {
  const [forceImport, setForceImport] = useState(false);

  const handlePreview = useCallback(async (data: string | ArrayBuffer) => {
    const { jobIds, errors } =
      await aironeApiClient.startImportEntriesPreview(data);
    if (errors.length > 0 || jobIds.length === 0) {
      // Applying only the accepted models would make the approved preview partial.
      throw new ImportPreviewFailure(
        errors.join(" / ") || "プレビューできるモデルがありませんでした",
      );
    }
    return jobIds;
  }, []);

  return (
    <AironeModal
      title={"アイテムのインポート"}
      description={"インポートするファイルを選択してください。"}
      caption={"※CSV形式のファイルは選択できません。"}
      open={openImportModal}
      onClose={closeImportModal}
    >
      <Box display="flex" alignItems="center">
        <Checkbox
          inputProps={{ "aria-label": "強制インポート" }}
          checked={forceImport}
          onChange={(event) => setForceImport(event.target.checked)}
        />
        <Typography variant={"body2"}>
          強制的にインポートする(短期間にインポートを繰り返したい場合に使用してください)
        </Typography>
      </Box>
      <Box my="8px">
        <ImportForm
          handleImport={(data: string | ArrayBuffer, previewJobIds: number[]) =>
            // Each model is paired with its own approved preview on the backend.
            aironeApiClient.importEntries(data, forceImport, previewJobIds)
          }
          handleCancel={closeImportModal}
          handlePreview={handlePreview}
        />
      </Box>
    </AironeModal>
  );
};
