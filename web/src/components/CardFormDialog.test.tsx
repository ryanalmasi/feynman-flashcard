import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CardFormDialog from "./CardFormDialog";

const HINT =
  "Wrap the hidden part in double braces, e.g. The capital of France is {{Paris}}.";

function setup(
  onSubmit = vi.fn().mockResolvedValue(null),
  initial?: { kind: "qa" | "cloze"; front: string; back: string },
) {
  render(
    <CardFormDialog
      open
      onOpenChange={() => {}}
      heading="Add card"
      submitLabel="Add"
      initial={initial}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

describe("CardFormDialog", () => {
  it("defaults to Q/A and requires both sides", async () => {
    const user = userEvent.setup();
    const onSubmit = setup();
    expect(screen.getByRole("button", { name: "Q/A" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Front"), "Q");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Front and back are both required.",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("Cloze shows the exact hint and submits with an empty back", async () => {
    const user = userEvent.setup();
    const onSubmit = setup();
    await user.click(screen.getByRole("button", { name: "Cloze" }));
    expect(screen.getByRole("button", { name: "Cloze" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText(HINT)).toBeInTheDocument();
    expect(screen.getByLabelText("Note (optional)")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Front"), "Sky is {{{{blue}}");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(onSubmit).toHaveBeenCalledWith({
      kind: "cloze",
      front: "Sky is {{blue}}",
      back: "",
    });
  });

  it("shows a server 422 message", async () => {
    const user = userEvent.setup();
    setup(
      vi.fn().mockResolvedValue("Cloze cards need exactly one {{answer}}."),
    );
    await user.click(screen.getByRole("button", { name: "Cloze" }));
    await user.type(screen.getByLabelText("Front"), "no blank");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cloze cards need exactly one {{answer}}.",
    );
  });

  it("opens a cloze card with the toggle on Cloze", () => {
    setup(undefined, { kind: "cloze", front: "A {{b}} c", back: "note" });
    expect(screen.getByRole("button", { name: "Cloze" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText("Note (optional)")).toHaveValue("note");
  });
});
