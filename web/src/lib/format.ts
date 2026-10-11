/** Number/date formatting. All money is INR; amounts render in en-IN grouping (12,34,567). */
const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const plain = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function formatINR(n: number, o: { decimals?: boolean; signed?: boolean } = {}): string {
  const body = (o.decimals ? inr2 : inr0).format(Math.abs(n));
  if (n < 0) return `−${body}`;
  return o.signed && n > 0 ? `+${body}` : body;
}

/** ₹1.2K, ₹3.4L (lakh), ₹1.1Cr (crore): Indian compact notation for chart axes. */
export function formatCompactINR(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "−" : "";
  const f = (v: number, s: string) => `${sign}₹${v >= 100 ? v.toFixed(0) : v.toFixed(1).replace(/\.0$/, "")}${s}`;
  if (a >= 1e7) return f(a / 1e7, "Cr");
  if (a >= 1e5) return f(a / 1e5, "L");
  if (a >= 1e3) return f(a / 1e3, "K");
  return `${sign}₹${Math.round(a)}`;
}

export const formatNumber = (n: number): string => plain.format(n);
export const formatPct = (n: number, digits = 0): string => `${n.toFixed(digits)}%`;

const dayFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
const monthFmt = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" });

export const formatDay = (iso: string | Date): string => dayFmt.format(new Date(iso));
export const formatTime = (iso: string | Date): string => timeFmt.format(new Date(iso));
export const formatMonthYear = (d: Date): string => monthFmt.format(d);

/** "Today · 14:32", "Yesterday · 09:10", otherwise "5 Oct · 14:32". */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((startOf(now) - startOf(d)) / 86_400_000);
  const day = diff === 0 ? "Today" : diff === 1 ? "Yesterday" : formatDay(d);
  return `${day} · ${formatTime(d)}`;
}
