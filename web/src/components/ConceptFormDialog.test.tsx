import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ConceptFormDialog from "./ConceptFormDialog";

const renderDialog = (onSubmit = vi.fn().mockResolvedValue(null)) => {
  const onOpenChange = vi.fn();
  render(
    <ConceptFormDialog
      open
      onOpenChange={onOpenChange}
      heading="Add concept"
      submitLabel="Add"
      onSubmit={onSubmit}
    />,
  );
  return { onSubmit, onOpenChange };
};

describe("ConceptFormDialog", () => {
  it("labels every field and shows the hints", () => {
    renderDialog();
    for (const label of [
      "Title",
      "Explanation",
      "Importance",
      "Key terms",
      "Misconceptions",
      "Pages",
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(
      screen.getByText("One per line: term: synonym, synonym"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Comma-separated, e.g. 3, 4, 7"),
    ).toBeInTheDocument();
    const options = Array.from(
      (screen.getByLabelText("Importance") as HTMLSelectElement).options,
    ).map((o) => [o.value, o.text]);
    expect(options).toEqual([
      ["core", "Core"],
      ["supporting", "Supporting"],
      ["detail", "Detail"],
    ]);
  });

  it("requires a title and an explanation", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits parsed values and closes on success", async () => {
    const user = userEvent.setup();
    const { onSubmit, onOpenChange } = renderDialog();
    await user.type(screen.getByLabelText("Title"), " T ");
    await user.type(screen.getByLabelText("Explanation"), "E");
    await user.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    expect(onSubmit).toHaveBeenCalledWith({
      title: "T",
      explanation: "E",
      importance: "core",
      key_terms: [],
      misconceptions: [],
      source_pages: [],
    });
  });

  it("keeps the dialog open and shows a returned error", async () => {
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog(
      vi.fn().mockResolvedValue("Server says no."),
    );
    await user.type(screen.getByLabelText("Title"), "T");
    await user.type(screen.getByLabelText("Explanation"), "E");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Server says no.",
    );
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
