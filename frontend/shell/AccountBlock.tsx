import { useMutation, useQueryClient } from "@tanstack/react-query";

import { formatReports } from "../api/format";
import { Button } from "../ui/Button";
import styles from "./AccountBlock.module.css";
import { signOut, useMe } from "./session";

function initials(name: string | null, email: string): string {
  const source = (name ?? "").trim() || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? (parts[1]?.[0] ?? "") : "")).toUpperCase();
}

/**
 * Who is signed in, how many reports they have (from the server, never counted here) and the way out. Signing out
 * hides the person's data at once; the session boundary (RequireSession) then shows sign-in once the server
 * confirmed it, or an "unconfirmed" notice with a retry when it could not (shell/session.tsx `signOut`).
 */
// GDPR[personal-data]: shows the signed-in person's name or e-mail address and report balance, in memory only (RM-271)
export function AccountBlock() {
  const me = useMe();
  const client = useQueryClient();
  const leave = useMutation({ mutationFn: () => signOut(client) });
  return (
    <div className={styles["account"]}>
      <div className={styles["who"]}>
        <span className={styles["avatar"]} aria-hidden="true">
          {initials(me.name, me.email)}
        </span>
        <span className={styles["details"]}>
          <strong>{me.name ?? me.email}</strong>
          <span>{formatReports(me.credit_balance)} na koncie</span>
        </span>
      </div>
      <Button type="button" small fill busy={leave.isPending} onClick={() => leave.mutate()}>
        Wyloguj się
      </Button>
    </div>
  );
}
