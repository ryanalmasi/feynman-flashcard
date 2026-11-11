import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ClozeText from "./ClozeText";

const front = "The capital of France is {{Paris}}.";

describe("ClozeText", () => {
  it("hides the answer behind a blank", () => {
    const { container } = render(<ClozeText front={front} reveal={false} />);
    expect(container).toHaveTextContent("The capital of France is _____.");
    expect(screen.queryByText("Paris")).not.toBeInTheDocument();
  });
  it("reveals the full sentence with the answer emphasised", () => {
    const { container } = render(<ClozeText front={front} reveal />);
    expect(container).toHaveTextContent("The capital of France is Paris.");
    const strong = screen.getByText("Paris");
    expect(strong.tagName).toBe("STRONG");
    expect(strong).toHaveClass("font-semibold", "text-primary");
  });
  it("renders an unparseable front as is", () => {
    const { container } = render(
      <ClozeText front="plain {{x" reveal={false} />,
    );
    expect(container).toHaveTextContent("plain {{x");
  });
  it("never injects markup", () => {
    const { container } = render(<ClozeText front="a <b>x</b> {{y}}" reveal />);
    expect(container.querySelector("b")).toBeNull();
  });
});
