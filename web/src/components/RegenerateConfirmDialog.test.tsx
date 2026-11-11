import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RegenerateConfirmDialog from "./RegenerateConfirmDialog";

describe("RegenerateConfirmDialog", () => {
  it("shows the exact sentence with N and M, and confirms with Generate", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <RegenerateConfirmDialog
        open
        onOpenChange={onOpenChange}
        counts={{ replace: 3, accepted: 1 }}
        onConfirm={onConfirm}
      />,
    );
    const dialog = screen.getByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "This replaces 3 AI-generated cards you haven't edited (1 of them already accepted). Your own cards and cards you've edited are kept.",
      ),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Generate" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Cancel does not confirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <RegenerateConfirmDialog
        open
        onOpenChange={onOpenChange}
        counts={{ replace: 2, accepted: 0 }}
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
