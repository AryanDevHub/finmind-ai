import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, formatDetail, onSessionExpired, session } from "@/lib/api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("api client", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); session.set("old-token"); });
  afterEach(() => { vi.unstubAllGlobals(); session.clear(); });

  const auth = (call: number) => (fetchMock.mock.calls[call]![1] as RequestInit).headers as Record<string, string>;

  it("sends the bearer token and parses JSON", async () => {
    fetchMock.mockResolvedValueOnce(json({ ok: 1 }));
    expect(await api<{ ok: number }>("/thing")).toEqual({ ok: 1 });
    expect(auth(0).Authorization).toBe("Bearer old-token");
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/thing");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ detail: "expired" }, 401))
      .mockResolvedValueOnce(json({ access_token: "new-token" }))
      .mockResolvedValueOnce(json({ ok: 1 }));
    expect(await api("/thing")).toEqual({ ok: 1 });
    expect(fetchMock.mock.calls[1]![0]).toBe("/api/auth/refresh");
    expect(auth(2).Authorization).toBe("Bearer new-token");
    expect(session.token).toBe("new-token");
  });

  it("single-flights concurrent refreshes (a rotating token must only be used once)", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/auth/refresh") return json({ access_token: "fresh" });
      return (fetchMock.mock.calls.filter((c) => c[0] === url).length <= 1) ? json({}, 401) : json({ ok: true });
    });
    await Promise.all([api("/a"), api("/b"), api("/c")]);
    expect(fetchMock.mock.calls.filter((c) => c[0] === "/api/auth/refresh")).toHaveLength(1);
  });

  it("drops the session and notifies listeners when refresh fails", async () => {
    const expired = vi.fn();
    const off = onSessionExpired(expired);
    fetchMock.mockResolvedValueOnce(json({}, 401)).mockResolvedValueOnce(json({ detail: "bad" }, 401));
    await expect(api("/thing")).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledOnce();
    expect(session.token).toBeNull();
    off();
  });

  it("never tries to refresh for /auth/* or when auth is disabled", async () => {
    fetchMock.mockResolvedValue(json({ detail: "Incorrect username or password" }, 401));
    await expect(api("/auth/login", { method: "POST", form: { username: "a", password: "b" }, auth: false })).rejects.toMatchObject({ detail: "Incorrect username or password" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(auth(0).Authorization).toBeUndefined();
    expect((fetchMock.mock.calls[0]![1] as RequestInit).body).toBeInstanceOf(URLSearchParams);
  });

  it("surfaces network failures and 204s sensibly", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api("/x")).rejects.toMatchObject({ status: 0, detail: expect.stringContaining("Can't reach") });
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    expect(await api("/x", { method: "DELETE" })).toBeUndefined();
  });

  it("formats FastAPI error shapes", () => {
    expect(formatDetail({ detail: "nope" }, 400)).toBe("nope");
    expect(formatDetail({ detail: [{ loc: ["body", "amount"], msg: "must be > 0" }, { loc: ["body", "category"], msg: "invalid" }] }, 422)).toBe("amount: must be > 0; category: invalid");
    expect(formatDetail(null, 500)).toBe("Request failed (500)");
    expect(new ApiError(404, "x")).toBeInstanceOf(Error);
  });
});
