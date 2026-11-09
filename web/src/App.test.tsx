import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { AuthProvider } from "./auth/AuthProvider";

describe("App", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the not-found page for unknown routes", () => {
    vi.stubGlobal("fetch", () => new Promise(() => {}));
    render(
      <MemoryRouter initialEntries={["/does-not-exist"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Page not found")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to your study sets" }),
    ).toHaveAttribute("href", "/sets");
  });
});
