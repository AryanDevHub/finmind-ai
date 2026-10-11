import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { BankConnection } from "@/components/BankConnectCard";

export const bankKeys = {
  connections: ["bank-connections"] as const,
};

export const useBankConnections = () =>
  useQuery({
    queryKey: bankKeys.connections,
    queryFn: ({ signal }) => api<BankConnection[]>("/api/bank/connections", { signal }),
    refetchInterval: 30_000,
  });

export function useConnectBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (phone: string) =>
      api<{ consent_id: string; redirect_url: string; status: string }>("/api/bank/connect", {
        method: "POST",
        json: { phone },
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: bankKeys.connections }),
  });
}

export function useSyncBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (connectionId: string) => api("/api/bank/sync/" + connectionId, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: bankKeys.connections }),
  });
}

export function useDisconnectBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (connectionId: string) => api("/api/bank/connections/" + connectionId, { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: bankKeys.connections }),
  });
}
