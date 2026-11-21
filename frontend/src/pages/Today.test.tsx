import { render, screen, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Today from "./Today";
import sample from "../../public/sample_run.json";

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const renderToday = () =>
  render(
    <QueryClientProvider client={client()}>
      <Today />
    </QueryClientProvider>,
  );

it("renders problems, explanations and the rule badge", async () => {
  globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(sample)));
  renderToday();
  expect(await screen.findByText(/KNP-03 is at 208% of capacity/)).toBeInTheDocument();
  expect(screen.getByText(/0 rule breaks/)).toBeInTheDocument();
  expect(screen.getAllByText(/SHW-02/).length).toBeGreaterThan(0);
});

it("snapshot mode shows a banner and disables approve (no silent fake success)", async () => {
  globalThis.fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error("asleep"))
    .mockResolvedValueOnce(new Response(JSON.stringify(sample)));
  renderToday();
  expect(await screen.findByText(/Snapshot/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Retry live/ })).toBeInTheDocument();
  const approve = screen.getAllByRole("button", { name: /^Approve / })[0];
  expect(approve).toBeDisabled();
  expect(screen.getAllByRole("button", { name: /Approve all/ })[0]).toBeDisabled();
});

it("a run with no moves shows a friendly empty state", async () => {
  const empty = { ...sample, problems: [], groups: [], summary: { ...sample.summary, n_groups: 0, n_moves: 0, units: 0 } };
  globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(empty)));
  renderToday();
  expect(await screen.findByText(/No stock in the wrong place today/)).toBeInTheDocument();
});

it("null evidence renders as a dash, never null or NaN", async () => {
  const g = { ...sample.groups[0], group_id: "GX", evidence: { ...sample.groups[0].evidence, from_cover_before: null, to_vel_daily: null, lift: null, age_days: null } };
  const run = { ...sample, problems: [{ problem_id: "PX", kind: "CAPACITY", title: "Test card", detail: "d", group_ids: ["GX"] }], groups: [g] };
  globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(run)));
  renderToday();
  const card = (await screen.findByText("Test card")).closest("section")!;
  fireEvent.click(within(card).getByRole("button", { name: /Details/ }));
  const details = await within(card).findByTestId("group-details");
  expect(details.textContent).not.toMatch(/null|NaN|undefined/);
  expect(details.textContent).toContain("—");
});
