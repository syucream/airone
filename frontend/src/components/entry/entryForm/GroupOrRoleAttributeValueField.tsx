import {
  Autocomplete,
  Box,
  TextField,
  Typography,
  CircularProgress,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import { FC, useState } from "react";
import { Control, Controller, UseFormSetValue } from "react-hook-form";

import { usePagodaSWR } from "../../../hooks/usePagodaSWR";

import { Schema } from "./EntryFormSchema";

import { useTranslation } from "hooks/useTranslation";
import { fuzzyMatch } from "services/StringUtil";
import { getStagedErrorStyle } from "utils/styleUtils";

const StyledTypography = styled(Typography)(() => ({
  color: "rgba(0, 0, 0, 0.6)",
}));

const StyledBox = styled(Box)(() => ({
  display: "flex",
  alignItems: "center",
}));

export interface GroupOrRoleFieldProps {
  attrId: number;
  control: Control<Schema>;
  setValue: UseFormSetValue<Schema>;
  multiple?: boolean;
  isDisabled?: boolean;
}

type Option = { id: number; name: string };

interface Props extends GroupOrRoleFieldProps {
  kind: "group" | "role";
  loadOptions: (query?: string) => Promise<Option[]>;
}

const fields = {
  group: {
    single: "asGroup",
    multiple: "asArrayGroup",
    caption: "entryForm.groupField.selectGroup",
  },
  role: {
    single: "asRole",
    multiple: "asArrayRole",
    caption: "entryForm.roleField.selectRole",
  },
} as const;

export const GroupOrRoleAttributeValueField: FC<Props> = ({
  attrId,
  control,
  setValue,
  kind,
  loadOptions,
  multiple = false,
  isDisabled = false,
}) => {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");
  const config = fields[kind];
  const valueKey = multiple ? config.multiple : config.single;
  const name = `attrs.${attrId}.value.${valueKey}` as const;

  const { data: options = [], isLoading: loading } = usePagodaSWR(
    [`${kind}Options`, inputValue],
    async () => {
      const matches = await loadOptions(inputValue);
      const choices =
        matches.length === 0 && inputValue ? await loadOptions() : matches;
      return choices.map(({ id, name }) => ({ id, name }));
    },
    // revalidateOnFocus is disabled so a transient failure of a background
    // refetch cannot crash the entry form the user is editing.
    { keepPreviousData: true, revalidateOnFocus: false },
  );

  const handleChange = (value: Option | Option[] | null) => {
    if (!multiple && value != null && !Array.isArray(value)) {
      setInputValue(value.name);
    } else if (multiple) {
      setInputValue("");
    }
    setValue(name, value ?? (multiple ? [] : null), {
      shouldDirty: true,
      shouldValidate: true,
    });
  };

  return (
    <Box>
      <StyledTypography variant="caption">{t(config.caption)}</StyledTypography>
      <StyledBox>
        <Controller
          name={name}
          control={control}
          render={({ field, fieldState: { error, isDirty } }) => (
            <Autocomplete<Option, boolean, false, false>
              fullWidth
              multiple={multiple}
              selectOnFocus
              clearOnBlur={false}
              loading={loading}
              options={options}
              filterOptions={(options, state) =>
                options.filter((option) =>
                  fuzzyMatch(option.name, state.inputValue),
                )
              }
              value={field.value ?? (multiple ? [] : null)}
              inputValue={
                inputValue ||
                (!multiple && field.value != null && !Array.isArray(field.value)
                  ? field.value.name
                  : "")
              }
              getOptionLabel={(option) => option.name}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              onChange={(_, value) => handleChange(value)}
              onInputChange={(_, value, reason) => {
                if (reason === "input" || reason === "clear") {
                  setInputValue(value);
                }
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  error={!!error}
                  helperText={error?.message}
                  size="small"
                  placeholder={multiple ? "" : "-NOT SET-"}
                  sx={getStagedErrorStyle(!!error, isDirty)}
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {loading ? <CircularProgress size={20} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
              disabled={isDisabled}
            />
          )}
        />
      </StyledBox>
    </Box>
  );
};
