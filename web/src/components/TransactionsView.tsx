import { useToast } from "@/components/ui/Toast";
import { useDeleteTransaction, useTransactions } from "@/lib/queries";
import { TransactionLedger } from "./TransactionLedger";

/** Full ledger with filters and search. Click an expense to open its ML diagnostics. */
export function TransactionsView() {
  const { data = [], isPending } = useTransactions();
  const del = useDeleteTransaction();
  const toast = useToast();
  return (
    <TransactionLedger transactions={data} loading={isPending}
      onDelete={(id) => del.mutate(id, { onSuccess: () => toast.push({ tone: "info", title: "Transaction deleted" }), onError: () => toast.push({ tone: "error", title: "Couldn't delete", body: "Nothing was changed." }) })} />
  );
}
