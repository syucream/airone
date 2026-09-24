import { Entity } from "@dmm-com/airone-apiclient-typescript-fetch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import { FC, useState } from "react";
import { Control, useFieldArray } from "react-hook-form";
import { UseFormSetValue } from "react-hook-form/dist/types/form";

import { AttributeField } from "./AttributeField";
import { Schema } from "./EntityFormSchema";

import { useTranslation } from "hooks/useTranslation";
import { AttributeTypes } from "services/Constants";

const HeaderTableRow = styled(TableRow)(({}) => ({
  backgroundColor: "#455A64",
}));

const HeaderTableCell = styled(TableCell)(({}) => ({
  color: "#FFFFFF",
  boxSizing: "border-box",
}));

const StyledTableBody = styled(TableBody)({
  "tr:nth-of-type(odd)": {
    backgroundColor: "white",
  },
  "tr:nth-of-type(even)": {
    backgroundColor: "#607D8B0A",
  },
  "& td": {
    padding: "8px",
  },
});

const HighlightedTableRow = styled(TableRow)(({}) => ({
  "@keyframes highlighted": {
    from: {
      backgroundColor: "#6B8998",
    },
  },
  animation: "highlighted 1s ease 0s 1",
}));

interface Props {
  control: Control<Schema>;
  setValue: UseFormSetValue<Schema>;
  referralEntities: Entity[];
}

export const AttributesFields: FC<Props> = ({
  control,
  setValue,
  referralEntities,
}) => {
  const { t } = useTranslation();
  const { fields, insert, remove, swap } = useFieldArray({
    control,
    name: "attrs",
    keyName: "key", // NOTE: attr has 'id' field conflicts default key name
  });

  const [latestChangedIndex, setLatestChangedIndex] = useState<number | null>(
    null,
  );

  const handleAppendAttribute = (index: number) => {
    insert(index + 1, {
      name: "",
      type: AttributeTypes.string.type,
      isMandatory: false,
      isDeleteInChain: false,
      isSummarized: false,
      isWritable: true,
      referral: [],
      note: "",
      defaultValue: undefined, // Explicitly initialize defaultValue
      nameOrder: "0",
      namePrefix: "",
      namePostfix: "",
    });
  };

  const handleDeleteAttribute = (index: number) => {
    remove(index);
  };

  const handleChangeOrderAttribute = (index: number, order: number) => {
    const newIndex = index - order;
    swap(newIndex, index);
    setLatestChangedIndex(newIndex);
  };

  return (
    <>
      <Typography variant="h4" align="center" my="16px">
        {t("entity.form.attributesTitle")}
      </Typography>

      <Table id="table_attribute_list">
        <TableHead>
          <HeaderTableRow>
            <HeaderTableCell width="300px">
              {t("entity.form.attrNameHeader")}
            </HeaderTableCell>
            <HeaderTableCell width="300px">
              {t("entity.form.attrTypeHeader")}
            </HeaderTableCell>
            <HeaderTableCell width="200px">
              {t("entity.form.defaultValueHeader")}
            </HeaderTableCell>
            <HeaderTableCell width="100px">
              {t("entity.form.reorderHeader")}
            </HeaderTableCell>
            <HeaderTableCell width="100px">
              {t("common.delete")}
            </HeaderTableCell>
            <HeaderTableCell width="100px">
              {t("entity.form.addHeader")}
            </HeaderTableCell>
            <HeaderTableCell width="100px">
              {t("common.details")}
            </HeaderTableCell>
          </HeaderTableRow>
        </TableHead>
        <StyledTableBody>
          <>
            {fields.map((field, index) => {
              const StyledTableRow =
                index === latestChangedIndex ? HighlightedTableRow : TableRow;
              return (
                <StyledTableRow key={field.key}>
                  <AttributeField
                    referralEntities={referralEntities}
                    handleAppendAttribute={handleAppendAttribute}
                    handleDeleteAttribute={handleDeleteAttribute}
                    handleChangeOrderAttribute={handleChangeOrderAttribute}
                    control={control}
                    setValue={setValue}
                    maxIndex={fields.length - 1}
                    attrId={field.id}
                    index={index}
                  />
                </StyledTableRow>
              );
            })}
            {fields.length === 0 && (
              <TableRow>
                <AttributeField
                  referralEntities={referralEntities}
                  handleAppendAttribute={handleAppendAttribute}
                  handleDeleteAttribute={handleDeleteAttribute}
                  handleChangeOrderAttribute={handleChangeOrderAttribute}
                  control={control}
                  setValue={setValue}
                  maxIndex={0}
                />
              </TableRow>
            )}
          </>
        </StyledTableBody>
      </Table>
    </>
  );
};
