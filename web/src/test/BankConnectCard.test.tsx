import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BankConnectCard, type BankConnection } from "@/components/BankConnectCard";
import { ToastProvider } from "@/components/ui/Toast";
import * as apiModule from "@/lib/api";

beforeEach(() => {
  window.matchMedia = ((q: string) => ({
    matches: q.includes("reduce"),
    media: q,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
});

const wrap = (ui: ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>
  );
};

describe("BankConnectCard", () => {
  const sampleConnections: BankConnection[] = [
    {
      id: "conn-1",
      fip_name: "HDFC Bank",
      status: "ACTIVE",
      last_synced_at: new Date(Date.now() - 3600 * 1000).toISOString(),
      consent_expiry: "2027-01-01T00:00:00Z",
    },
    {
      id: "conn-2",
      fip_name: "State Bank of India",
      status: "PENDING",
      last_synced_at: null,
      consent_expiry: "2027-01-01T00:00:00Z",
    },
  ];

  it("renders bank connections with accurate status and relative timestamps", () => {
    wrap(<BankConnectCard connections={sampleConnections} isLoading={false} onRefresh={vi.fn()} />);

    expect(screen.getByText("Bank Sync")).toBeInTheDocument();
    expect(screen.getByText("HDFC Bank")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("1 hour ago")).toBeInTheDocument();

    expect(screen.getByText("State Bank of India")).toBeInTheDocument();
    expect(screen.getByText("Action Required")).toBeInTheDocument();
    expect(screen.getByText("Never synced")).toBeInTheDocument();

    expect(screen.getByText("Read-Only Access")).toBeInTheDocument();
    expect(screen.getByText("No Login Details Stored")).toBeInTheDocument();
    expect(screen.getByText("Revoke Consent Anytime")).toBeInTheDocument();
  });

  it("opens modal and handles phone consent initiation flow", async () => {
    const onRefresh = vi.fn();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const apiSpy = vi.spyOn(apiModule, "api").mockResolvedValue({
      consent_id: "c-123",
      redirect_url: "https://sandbox.setu.co/consent/ui?handle=h-1",
      status: "PENDING",
    });

    wrap(<BankConnectCard connections={sampleConnections} isLoading={false} onRefresh={onRefresh} />);

    // Click CTA
    await userEvent.click(screen.getByRole("button", { name: /Connect Bank Account/i }));
    expect(await screen.findByRole("dialog", { name: /Connect Bank Account/i })).toBeInTheDocument();

    // Type 10-digit mobile number
    const phoneInput = screen.getByLabelText(/Linked Mobile Number/i);
    await userEvent.type(phoneInput, "9876543210");

    // Submit
    const submitBtn = screen.getByRole("button", { name: /Continue to Aggregator/i });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiSpy).toHaveBeenCalledWith("/api/bank/connect", {
        method: "POST",
        json: { phone: "9876543210" },
      });
    });

    expect(openSpy).toHaveBeenCalledWith(
      "https://sandbox.setu.co/consent/ui?handle=h-1",
      "_blank",
      "noopener,noreferrer"
    );

    apiSpy.mockRestore();
    openSpy.mockRestore();
  });

  it("triggers manual bank sync and calls api", async () => {
    const onRefresh = vi.fn();
    const apiSpy = vi.spyOn(apiModule, "api").mockResolvedValue({ status: "queued" });

    wrap(<BankConnectCard connections={sampleConnections} isLoading={false} onRefresh={onRefresh} />);

    const syncButtons = screen.getAllByRole("button", { name: /Sync Now/i });
    await userEvent.click(syncButtons[0]!);

    await waitFor(() => {
      expect(apiSpy).toHaveBeenCalledWith("/api/bank/sync/conn-1", { method: "POST" });
    });
    expect(onRefresh).toHaveBeenCalled();

    apiSpy.mockRestore();
  });

  it("triggers disconnection and calls DELETE api", async () => {
    const onRefresh = vi.fn();
    const apiSpy = vi.spyOn(apiModule, "api").mockResolvedValue(undefined);

    wrap(<BankConnectCard connections={sampleConnections} isLoading={false} onRefresh={onRefresh} />);

    const unlinkButtons = screen.getAllByTitle(/Revoke bank connection consent/i);
    await userEvent.click(unlinkButtons[0]!);

    await waitFor(() => {
      expect(apiSpy).toHaveBeenCalledWith("/api/bank/connections/conn-1", { method: "DELETE" });
    });
    expect(onRefresh).toHaveBeenCalled();

    apiSpy.mockRestore();
  });
});
