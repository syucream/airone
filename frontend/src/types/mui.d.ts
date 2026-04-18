import "@mui/material/styles";

declare module "@mui/material/styles" {
  interface Palette {
    tableHeader: { background: string; text: string };
    tableRow: { alternateBackground: string };
    surface: { search: string };
    header: { versionText: string };
  }
  interface PaletteOptions {
    tableHeader?: { background: string; text: string };
    tableRow?: { alternateBackground: string };
    surface?: { search: string };
    header?: { versionText: string };
  }
}
