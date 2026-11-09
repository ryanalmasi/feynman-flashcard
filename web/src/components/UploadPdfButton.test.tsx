import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import UploadPdfButton from "./UploadPdfButton";
import { setCsrfToken } from "@/api/client";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const routes = (
  <Routes>
    <Route path="/sets" element={<UploadPdfButton />} />
    <Route path="/sets/:id" element={<h1>Set detail</h1>} />
  </Routes>
);

const MAX = 20 * 1024 * 1024;

function pdf(name = "notes.pdf", size?: number) {
  const f = new File(["%PDF-1.4"], name, { type: "application/pdf" });
  if (size !== undefined) Object.defineProperty(f, "size", { value: size });
  return f;
}

const uploadOut = {
  study_set: { id: "set-9" },
  document: { id: "d1", study_set_id: "set-9", status: "processing" },
};

function setup(upload?: (req: Request) => Response | Promise<Response>) {
  const fetchMock = stubFetch({
    "GET /auth/session": () => json(session, 200),
    ...(upload ? { "POST /documents": upload } : {}),
  });
  renderAt("/sets", routes);
  return fetchMock;
}

const posts = (m: ReturnType<typeof vi.fn>) =>
  m.mock.calls.filter((c) => (c[0] as Request).method === "POST");

beforeEach(() => {
  vi.mocked(toast.error).mockClear();
  vi.mocked(toast.success).mockClear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe("UploadPdfButton", () => {
  it("rejects a non-pdf name with 'Choose a PDF file.' and sends nothing", async () => {
    const fetchMock = setup();
    const input = await screen.findByTestId("pdf-input");
    await userEvent.upload(input, pdf("notes.txt"), { applyAccept: false });
    expect(toast.error).toHaveBeenCalledWith("Choose a PDF file.");
    expect(posts(fetchMock)).toHaveLength(0);
  });

  it("rejects > 20 MB with 'This file is larger than 20 MB.' and sends nothing", async () => {
    const fetchMock = setup();
    const input = await screen.findByTestId("pdf-input");
    await userEvent.upload(input, pdf("big.pdf", MAX + 1));
    expect(toast.error).toHaveBeenCalledWith("This file is larger than 20 MB.");
    expect(posts(fetchMock)).toHaveLength(0);
  });

  it("accepts a file of exactly 20 MiB and an uppercase .PDF name", async () => {
    const fetchMock = setup(() => json(uploadOut, 202));
    const input = await screen.findByTestId("pdf-input");
    await userEvent.upload(input, pdf("BIG.PDF", MAX), { applyAccept: false });
    await waitFor(() => expect(posts(fetchMock)).toHaveLength(1));
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("posts multipart with field 'file' and the CSRF header, then navigates to the set", async () => {
    let seen: Request | undefined;
    let rawBody = "";
    setup(async (req) => {
      seen = req.clone();
      rawBody = await req.text();
      return json(uploadOut, 202);
    });
    const input = await screen.findByTestId("pdf-input");
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.upload(input, pdf());
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("/sets/set-9"),
    );
    expect(seen!.headers.get("X-CSRF-Token")).toBe("t");
    expect(seen!.headers.get("Content-Type")).toMatch(
      /^multipart\/form-data; boundary=/,
    );
    // jsdom's File is not undici's, so the part's filename/content degrade
    // in this environment; the field name is what we pin here.
    expect(rawBody).toContain('Content-Disposition: form-data; name="file"');
    expect(toast.success).toHaveBeenCalledWith("Upload received. Processing…");
  });

  it("shows 'Uploading…' and disables the button while busy", async () => {
    let release!: () => void;
    setup(
      () =>
        new Promise<Response>((res) => {
          release = () => res(json(uploadOut, 202));
        }),
    );
    const input = await screen.findByTestId("pdf-input");
    await userEvent.upload(input, pdf());
    const btn = await screen.findByRole("button", { name: "Uploading…" });
    expect(btn).toBeDisabled();
    release();
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("/sets/set-9"),
    );
  });

  it.each([
    [413, "file_too_large", "That file is too large."],
    [415, "unsupported_file_type", "Only PDF files are supported."],
  ])("shows the server %i message", async (status, code, message) => {
    setup(() => json(apiError(code, message), status));
    const input = await screen.findByTestId("pdf-input");
    await userEvent.upload(input, pdf());
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
    expect(screen.getByTestId("where")).toHaveTextContent("/sets");
    expect(screen.getByRole("button", { name: "Upload PDF" })).toBeEnabled();
  });
});
