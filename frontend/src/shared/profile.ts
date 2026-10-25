/** The agent profile this browser works on. Sent as X-Eval-Profile on every API request; empty = the
 * server's default (EVAL_PROFILE, else copilot). Stored per browser; storage may be unavailable. */
const KEY = "eval-lab.profile";

let current: string | null = (() => {
  try { return localStorage.getItem(KEY) || null; } catch { return null; }
})();

export const getProfile = (): string | null => current;

export function setProfile(name: string | null): void {
  current = name || null;
  try {
    if (current) localStorage.setItem(KEY, current);
    else localStorage.removeItem(KEY);
  } catch { /* private mode etc.: keep it for this tab only */ }
}

export const profileHeaders = (): Record<string, string> => (current ? { "X-Eval-Profile": current } : {});
