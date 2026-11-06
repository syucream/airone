import { render, screen } from "@testing-library/react";

import { ErrorHandler } from "./ErrorHandler";
import { TestWrapper } from "./TestWrapper";

function BrokenChild({ error }: { error: unknown }): never {
  throw error;
}

test.each([
  { error: null, detail: "エラー詳細: null" },
  { error: 42, detail: "エラー詳細: 42" },
  {
    error: {
      toString() {
        throw new Error("Cannot stringify");
      },
    },
    detail: "エラー詳細:",
  },
])("shows the generic dialog with $detail", ({ error, detail }) => {
  render(
    <ErrorHandler>
      <BrokenChild error={error} />
    </ErrorHandler>,
    { wrapper: TestWrapper },
  );

  expect(
    screen.getByRole("dialog", { name: "エラーが発生しました" }),
  ).toBeInTheDocument();
  expect(screen.getByText(detail)).toBeInTheDocument();
});
