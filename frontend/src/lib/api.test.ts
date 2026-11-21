import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchLatest, decideMany, exportUrl } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("fetchLatest", () => {
  it("falls back to snapshot when API fails", async () => {
    const sample = { run_id: "SAMPLE", groups: [] };
    globalThis.fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValueOnce(new Response(JSON.stringify(sample)));
    const r = await fetchLatest();
    expect(r.source).toBe("snapshot");
    expect(r.run.run_id).toBe("SAMPLE");
  });

  it("uses live data when the API answers", async () => {
    const live = { run_id: "LIVE", groups: [] };
    globalThis.fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(live)));
    const r = await fetchLatest();
    expect(r.source).toBe("live");
    expect(r.run.run_id).toBe("LIVE");
  });

  it("treats a non-JSON (HTML) answer as API down", async () => {
    const sample = { run_id: "SAMPLE", groups: [] };
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("<!doctype html><html></html>", { headers: { "content-type": "text/html" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(sample)));
    const r = await fetchLatest();
    expect(r.source).toBe("snapshot");
  });
});

describe("decisions", () => {
  it("decideMany posts ids and returns the updated count", async () => {
    const f = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ updated: 2 })));
    globalThis.fetch = f;
    const n = await decideMany(["G1", "G2"], "approve");
    expect(n).toBe(2);
    const [url, init] = f.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/groups\/decision$/);
    expect(JSON.parse(init.body)).toEqual({ group_ids: ["G1", "G2"], decision: "approve" });
  });

  it("decideMany throws on a failed request (no silent success)", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce(new Response("nope", { status: 500 }));
    await expect(decideMany(["G1"], "reject")).rejects.toThrow();
  });

  it("exportUrl", () => {
    expect(exportUrl()).toMatch(/\/api\/export\.csv\?status=approved$/);
  });
});
