import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import report from "../public/dev.json";
import { slColour } from "./shared/tokens";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function serve(dev: unknown, status = 200) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("heldout") ? new Response("", { status: 404 }) : new Response(JSON.stringify(dev), { status }),
  );
}

describe("App", () => {
  it("shows a skeleton, then the grid and every section", async () => {
    serve(report);
    render(<App />);
    expect(screen.getByLabelText("Loading the results")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Three ways to staff the same weeks")).toBeTruthy());
    expect(screen.getByText("Paying for productive minutes, once")).toBeTruthy();
    expect(screen.getByText(/It has not been run yet/)).toBeTruthy();
  });

  it("recolours the grid for another design and explains a half hour when it is picked", async () => {
    serve(report);
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /^Exchange, week 1, Mon 08:00/ }).length).toBe(1));
    fireEvent.click(screen.getByRole("radio", { name: "Fixed roster" }));
    const cell = screen.getByRole("button", { name: /^Fixed roster, week 1, Mon 10:00/ });
    fireEvent.click(cell);
    expect(screen.getByText(/Week 1, Mon 10:00/)).toBeTruthy();
    expect(screen.getAllByText(/on the phone/).length).toBe(3);
  });

  it("says plainly when the report fails, and loads again", async () => {
    serve(report, 500);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    serve(report);
    fireEvent.click(screen.getByText("Load again"));
    await waitFor(() => expect(screen.getByText("Three ways to staff the same weeks")).toBeTruthy());
  });

  it("shows how to make a report when there is none", async () => {
    serve({ world: "D1" });
    render(<App />);
    await waitFor(() => expect(screen.getByText("No results yet.")).toBeTruthy());
  });
});

describe("slColour", () => {
  it("grades a half hour against the 80/20 target", () => {
    expect(slColour(0.9, 10)).toBe("var(--sl-on)");
    expect(slColour(0.75, 10)).toBe("var(--sl-near)");
    expect(slColour(0.5, 10)).toBe("var(--sl-short)");
    expect(slColour(0.1, 10)).toBe("var(--sl-lost)");
    expect(slColour(0, 0)).toBe("var(--sl-quiet)");
  });
});
