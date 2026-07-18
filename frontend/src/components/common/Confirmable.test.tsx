import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { Confirmable } from "./Confirmable";

describe("Confirmable", () => {
  it("shows dialog and handles confirmation", async () => {
    const onClickYes = jest.fn();
    render(
      <Confirmable
        componentGenerator={(open) => <button onClick={open}>Open</button>}
        dialogTitle="確認"
        onClickYes={onClickYes}
        content={<div>本当に実行しますか？</div>}
      />,
    );
    fireEvent.click(screen.getByText("Open"));
    expect(screen.getByText("確認")).toBeInTheDocument();
    expect(screen.getByText("本当に実行しますか？")).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByText("Yes"));
    });
    expect(onClickYes).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText("確認")).not.toBeInTheDocument();
    });
  });
});
