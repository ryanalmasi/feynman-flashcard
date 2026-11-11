import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AiBadge from "./AiBadge";

describe("AiBadge", () => {
  it("renders the AI label", () => {
    render(<AiBadge />);
    expect(screen.getByText("AI")).toBeInTheDocument();
  });
});
