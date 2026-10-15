import type { RowData } from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- the module augmentation must repeat the library's parameters
  interface ColumnMeta<TFeatures extends TableFeatures, TData extends RowData, TValue = unknown> {
    /** Right-aligned figures. */
    numeric?: boolean;
  }
}
