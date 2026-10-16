import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRightLeft,
  Building2,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Shield,
  Unlink,
  X,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { GlassCard } from "./ui/GlassCard";
import { Skeleton } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { softSpring, spring, tap } from "@/lib/motion";
import { api, ApiError } from "@/lib/api";

export interface BankConnection {
  id: string;
  fip_name: string;
  status: "PENDING" | "ACTIVE" | "REVOKED" | "EXPIRED";
  last_synced_at: string | null;
  consent_expiry: string;
  fip_id?: string;
  consent_start?: string;
  created_at?: string;
}

interface Props {
  connections: BankConnection[] | undefined;
  isLoading: boolean;
  onRefresh: () => void;
}

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return "Never synced";
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    if (diffMs < 0) return "Just now";
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "Just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin === 1) return "1 min ago";
    if (diffMin < 60) return `${diffMin} mins ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours === 1) return "1 hour ago";
    if (diffHours < 24) return `${diffHours} hours ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 30) return `${diffDays} days ago`;
    return new Date(isoString).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
  } catch {
    return "Unknown";
  }
}

export function BankConnectCard({ connections, isLoading, onRefresh }: Props) {
  const toast = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    const cleanPhone = phone.trim().replace(/\D/g, "");
    if (cleanPhone.length !== 10) {
      toast.push({
        tone: "warn",
        title: "Invalid Phone Number",
        body: "Please enter a valid 10-digit mobile number.",
      });
      return;
    }

    setIsConnecting(true);
    try {
      const res = await api<{ consent_id: string; redirect_url: string; status: string }>(
        "/api/bank/connect",
        {
          method: "POST",
          json: { phone: cleanPhone },
        }
      );

      toast.push({
        tone: "success",
        title: "Consent Initiated",
        body: "Opening Account Aggregator verification window...",
      });

      if (res.redirect_url) {
        window.open(res.redirect_url, "_blank", "noopener,noreferrer");
      }

      setModalOpen(false);
      setPhone("");
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Failed to initiate bank connection.";
      toast.push({
        tone: "error",
        title: "Connection Failed",
        body: msg,
      });
    } finally {
      setIsConnecting(false);
    }
  };

  const handleSync = async (connId: string, bankName: string) => {
    if (syncingId) return;
    setSyncingId(connId);
    try {
      await api(`/api/bank/sync/${connId}`, { method: "POST" });
      toast.push({
        tone: "success",
        title: "Sync Complete",
        body: `Updated transactions for ${bankName}.`,
      });
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : `Could not sync ${bankName}.`;
      toast.push({
        tone: "error",
        title: "Sync Failed",
        body: msg,
      });
    } finally {
      setSyncingId(null);
    }
  };

  const handleDisconnect = async (connId: string, bankName: string) => {
    if (revokingId) return;
    setRevokingId(connId);
    try {
      await api(`/api/bank/connections/${connId}`, { method: "DELETE" });
      toast.push({
        tone: "info",
        title: "Bank Disconnected",
        body: `Revoked consent for ${bankName}.`,
      });
      onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : `Could not disconnect ${bankName}.`;
      toast.push({
        tone: "error",
        title: "Disconnection Failed",
        body: msg,
      });
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <>
      <GlassCard className="p-6 md:p-7">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-brand">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight text-ink-1">Bank Sync</h2>
                <span className="rounded border border-emerald/20 bg-emerald/5 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-emerald">
                  RBI AA PROTOCOL
                </span>
              </div>
              <p className="text-xs text-ink-3">Live automated transaction streaming via Account Aggregator</p>
            </div>
          </div>

          <motion.button
            {...tap}
            onClick={() => setModalOpen(true)}
            className="btn-primary inline-flex items-center justify-center gap-2 text-xs sm:text-sm"
          >
            <Plus className="h-4 w-4" />
            <span>Connect Bank Account</span>
          </motion.button>
        </div>

        {/* Content Area */}
        <div className="mt-6 space-y-3">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.02] p-4"
                >
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded-lg" />
                    <div className="space-y-1.5">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-24" />
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-7 w-20 rounded-full" />
                    <Skeleton className="h-8 w-24 rounded-lg" />
                  </div>
                </div>
              ))}
            </div>
          ) : !connections || connections.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.015] py-9 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.04] text-ink-3">
                <ArrowRightLeft className="h-6 w-6 text-ink-3" />
              </div>
              <p className="text-sm font-medium text-ink-2">No bank accounts linked yet</p>
              <p className="mx-auto mt-1 max-w-sm text-xs text-ink-3">
                Securely stream real-time transactions directly into FinMind AI without sharing login credentials.
              </p>
              <motion.button
                {...tap}
                onClick={() => setModalOpen(true)}
                className="btn-ghost mt-4 text-xs text-signal"
              >
                Link account now
              </motion.button>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {connections.map((conn) => {
                const isSyncing = syncingId === conn.id;
                const isRevoking = revokingId === conn.id;

                return (
                  <motion.div
                    key={conn.id}
                    layout
                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.96 }}
                    transition={spring}
                    className="group relative flex flex-col justify-between gap-4 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 transition-all hover:border-white/[0.14] hover:bg-white/[0.035] sm:flex-row sm:items-center"
                  >
                    {/* Bank Info */}
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-void text-signal font-mono text-xs font-semibold">
                        {(conn.fip_name || "BNK").slice(0, 3).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="truncate text-sm font-semibold text-ink-1">
                            {conn.fip_name || "Bank Account"}
                          </h3>

                          {/* Status Badges */}
                          {isSyncing ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-400">
                              <span className="relative flex h-1.5 w-1.5">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
                                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-sky-500" />
                              </span>
                              Syncing
                            </span>
                          ) : conn.status === "ACTIVE" ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-gain/30 bg-gain/10 px-2 py-0.5 text-[11px] font-medium text-gain">
                              <span className="relative flex h-1.5 w-1.5">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gain opacity-75" />
                                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-gain" />
                              </span>
                              Connected
                            </span>
                          ) : conn.status === "PENDING" || conn.status === "EXPIRED" ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-warn/30 bg-warn/10 px-2 py-0.5 text-[11px] font-medium text-warn">
                              <span className="h-1.5 w-1.5 rounded-full bg-warn" />
                              Action Required
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-medium text-ink-3">
                              <span className="h-1.5 w-1.5 rounded-full bg-ink-4" />
                              Disconnected
                            </span>
                          )}
                        </div>

                        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-ink-3">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            <span>Synced:</span>
                            <span className="font-mono tabular-nums text-ink-2">
                              {formatRelativeTime(conn.last_synced_at)}
                            </span>
                          </span>

                          <span className="hidden sm:inline text-white/10">·</span>

                          <span className="flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-signal" />
                            <span>Auto-refresh active</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <motion.button
                        {...tap}
                        onClick={() => handleSync(conn.id, conn.fip_name)}
                        disabled={isSyncing || conn.status === "REVOKED"}
                        className="btn-ghost px-3 py-1.5 text-xs text-ink-1 hover:text-signal disabled:opacity-50"
                        title="Sync latest transactions now"
                      >
                        <RefreshCw
                          className={`h-3.5 w-3.5 ${
                            isSyncing ? "animate-spin text-signal" : ""
                          }`}
                        />
                        <span>{isSyncing ? "Syncing..." : "Sync Now"}</span>
                      </motion.button>

                      <motion.button
                        {...tap}
                        onClick={() => handleDisconnect(conn.id, conn.fip_name)}
                        disabled={isRevoking}
                        className="btn border border-white/10 bg-white/[0.02] p-2 text-ink-3 hover:border-danger/30 hover:bg-danger/10 hover:text-danger disabled:opacity-50"
                        title="Revoke bank connection consent"
                      >
                        {isRevoking ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Unlink className="h-3.5 w-3.5" />
                        )}
                      </motion.button>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>

        {/* Trust Badges */}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-[11px] text-ink-3">
          <div className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald shrink-0" />
            <span>Read-Only Statement Access</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald shrink-0" />
            <span>Zero Password Storage</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald shrink-0" />
            <span>Revoke Consent Anytime</span>
          </div>
        </div>
      </GlassCard>

      {/* Connect Modal */}
      <AnimatePresence>
        {modalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              className="absolute inset-0 bg-void/75 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !isConnecting && setModalOpen(false)}
            />

            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label="Connect Bank Account"
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              transition={softSpring}
              className="glass-elevated relative w-full max-w-md overflow-hidden p-6"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-brand">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-ink-1">Connect Bank Account</h3>
                    <p className="text-xs text-ink-3">Via RBI Licensed Account Aggregator</p>
                  </div>
                </div>

                <button
                  onClick={() => setModalOpen(false)}
                  disabled={isConnecting}
                  className="rounded-lg p-1.5 text-ink-3 hover:bg-surface hover:text-ink-1"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <form onSubmit={handleConnect} className="mt-5 space-y-4">
                <div>
                  <label htmlFor="bank-phone" className="label mb-2 block">
                    Linked Mobile Number
                  </label>
                  <div className="relative">
                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-sm text-ink-3">
                      +91
                    </span>
                    <input
                      id="bank-phone"
                      type="tel"
                      maxLength={10}
                      autoFocus
                      required
                      placeholder="9876543210"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                      disabled={isConnecting}
                      className="field pl-12 font-mono tabular-nums tracking-wider"
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-ink-3">
                    Enter the phone number registered with your bank accounts.
                  </p>
                </div>

                <div className="rounded-lg border border-emerald/20 bg-emerald/[0.04] p-3 text-xs text-ink-2">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-emerald shrink-0" />
                    <span>
                      FinMind AI never asks for bank passwords, MPIN, or debit card credentials.
                      Consent is approved securely via your phone OTP.
                    </span>
                  </div>
                </div>

                <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    disabled={isConnecting}
                    className="btn-ghost text-xs"
                  >
                    Cancel
                  </button>
                  <motion.button
                    {...tap}
                    type="submit"
                    disabled={isConnecting || phone.length !== 10}
                    className="btn-primary text-xs"
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <>
                        <span>Continue to Aggregator</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </>
                    )}
                  </motion.button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
