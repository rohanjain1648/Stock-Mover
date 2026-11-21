import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import Stores from "./Stores";
import Findings from "./Findings";
import Runs from "./Runs";
import sample from "../../public/sample_run.json";

const runs = [{ run_id: sample.run_id, generated_at: sample.generated_at, trigger: "schedule", n_groups: 278, passed: true }];
const log = [{ sent_at: "2026-11-21T07:01:00+05:30", channel: "email", to: "merch@example.com", subject: "Stock Mover · 278 moves", ok: true }];

function mockApi() {
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    const u = String(url);
    const body = u.includes("/api/runs/latest") ? sample : u.endsWith("/api/runs") ? runs : u.includes("/notifications/log") ? log : sample;
    return Promise.resolve(new Response(JSON.stringify(body)));
  });
}

const renderPage = (el: ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{el}</MemoryRouter>
    </QueryClientProvider>,
  );

it("Stores shows every store card", async () => {
  mockApi();
  renderPage(<Stores />);
  expect(await screen.findByText("KNP-03")).toBeInTheDocument();
  expect(screen.getByText("WH-KOL")).toBeInTheDocument();
  expect(screen.getByText("Lucknow")).toBeInTheDocument();
});

it("Findings groups flags under plain headings", async () => {
  mockApi();
  renderPage(<Findings />);
  expect(await screen.findByText("Over capacity")).toBeInTheDocument();
  expect(screen.getByText("Data to fix")).toBeInTheDocument();
  expect(screen.getByText(/Sold out — re-order, not slow/)).toBeInTheDocument();
});

it("Runs explains the schedule and lists history and notifications", async () => {
  mockApi();
  renderPage(<Runs />);
  expect(await screen.findByText(/Runs on its own/)).toBeInTheDocument();
  expect(await screen.findByText(/Stock Mover · 278 moves/)).toBeInTheDocument();
});
