export interface BankConnection {
  id: string;
  fip_id: string;
  fip_name: string;
  status: "PENDING" | "ACTIVE" | "REVOKED" | "EXPIRED";
  last_synced_at: string | null;
  consent_start: string;
  consent_expiry: string;
  created_at: string;
}

export interface ConnectBankResponse {
  consent_id: string;
  redirect_url: string;
  status: string;
}
