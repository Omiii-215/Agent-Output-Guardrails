// Development session: who the browser acts as. In development and test the API
// accepts an X-Dev-User header (the stub refuses to start elsewhere). Staging and
// production use OIDC sign-in instead; this module is the only place that changes.

export type DevSession = { subject: string; organizationId: string | null };

const KEY = "finguard.dev-session";

export const PERSONAS = [
  { subject: "operator@acme.test", label: "Accounts-payable operator" },
  { subject: "approver@acme.test", label: "Finance approver" },
  { subject: "approver2@acme.test", label: "Finance approver (₹50,000 limit)" },
  { subject: "auditor@acme.test", label: "Auditor (read-only)" },
  { subject: "author@acme.test", label: "Policy author" },
  { subject: "publisher@acme.test", label: "Policy publisher" },
  { subject: "admin@acme.test", label: "Organization administrator" },
  { subject: "operator@globex.test", label: "Globex operator (second tenant)" },
];

export function loadSession(): DevSession | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as DevSession) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: DevSession | null): void {
  try {
    if (session) window.localStorage.setItem(KEY, JSON.stringify(session));
    else window.localStorage.removeItem(KEY);
  } catch {
    // Storage can be unavailable (private mode); the session then lasts for the page only.
  }
}
