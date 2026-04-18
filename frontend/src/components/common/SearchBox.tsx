import SearchIcon from "@mui/icons-material/Search";
import { InputAdornment, SxProps, TextField, Theme } from "@mui/material";
import { styled } from "@mui/material/styles";
import { FC, KeyboardEvent, useRef } from "react";

const StyledTextField = styled(TextField)(({ theme }) => ({
  background: theme.palette.surface.search,
  "& fieldset": {
    borderColor: theme.palette.background.paper,
  },
}));

interface Props {
  placeholder: string;
  onChange?: React.ChangeEventHandler<HTMLTextAreaElement | HTMLInputElement>;
  onKeyPress?: (e: KeyboardEvent<HTMLDivElement>, value: string) => void;
  value?: string;
  defaultValue?: string;
  inputSx?: SxProps<Theme>;
  autoFocus?: boolean;
}

export const SearchBox: FC<Props> = ({
  placeholder,
  onChange,
  onKeyPress,
  value,
  defaultValue,
  inputSx,
  autoFocus,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <StyledTextField
      key={defaultValue}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon />
          </InputAdornment>
        ),
        sx: {
          borderRadius: "0px",
          ...inputSx,
        },
      }}
      placeholder={placeholder}
      fullWidth={true}
      defaultValue={defaultValue}
      value={value}
      onChange={onChange}
      onKeyDown={(e) => {
        if (onKeyPress && inputRef.current && e.key === "Enter") {
          onKeyPress(e, inputRef.current.value);
        }
      }}
      autoFocus={autoFocus}
      inputRef={inputRef}
    />
  );
};
