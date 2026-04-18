import {
  TableCell,
  TableRow,
  TableCellProps,
  TableRowProps,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import { SxProps, Theme } from "@mui/system";

type StyledTableRowProps = TableRowProps & {
  sx?: SxProps<Theme>;
};

type StyledTableCellProps = TableCellProps & {
  sx?: SxProps<Theme>;
};

export const HeaderTableRow: React.ComponentType<StyledTableRowProps> = styled(
  TableRow,
)<StyledTableRowProps>(({ theme }) => ({
  backgroundColor: theme.palette.tableHeader.background,
})) as React.ComponentType<StyledTableRowProps>;

export const HeaderTableCell: React.ComponentType<StyledTableCellProps> =
  styled(TableCell)<StyledTableCellProps>(({ theme }) => ({
    color: theme.palette.tableHeader.text,
    boxSizing: "border-box",
  })) as React.ComponentType<StyledTableCellProps>;

export const StyledTableRow: React.ComponentType<StyledTableRowProps> = styled(
  TableRow,
)<StyledTableRowProps>({
  "& td": {
    padding: "8px",
  },
}) as React.ComponentType<StyledTableRowProps>;
