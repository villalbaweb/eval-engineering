export const pct = (x: number | null | undefined, digits = 0): string =>
  x == null || Number.isNaN(x) ? "–" : `${(x * 100).toFixed(digits)}%`;

export const num = (x: number | null | undefined, digits = 2): string =>
  x == null || Number.isNaN(x) ? "–" : x.toFixed(digits);

export const signedPct = (x: number): string => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;

export const usd = (x: number | null | undefined): string => (x == null ? "n/a" : `$${x.toFixed(4)}`);

export const ago = (iso: string): string => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

/** Pass-rate → semantic colour class (never colour alone: the label is always shown too). */
export const rateClass = (r: number): string => (r >= 0.9 ? "good" : r >= 0.6 ? "warn" : "bad");
