import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrapEmpty } from "../api/client";
import { formatReports } from "../api/format";
import { Button } from "../ui/Button";
import styles from "./AccountBlock.module.css";
import { endSession, useMe } from "./session";
import { sendSessionSignal } from "./sessionBus";

function initials(name: string | null, email: string): string {
  const source = (name ?? "").trim() || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? (parts[1]?.[0] ?? "") : "")).toUpperCase();
}

/**
 * Who is signed in, how many reports they have (from the server, never counted here) and the way out. Signing out
 * ends the session in this tab whatever the request's outcome (on success the server clears the cookie; on a network
 * failure the next request answers 401), tells the other tabs, and the session boundary (RequireSession) then
 * leaves for the sign-in page, whether or not this block is still mounted (the mobile sheet closes with it).
 */
// GDPR[personal-data]: shows the signed-in person's name or e-mail address and report balance, in memory only (RM-271)
export function AccountBlock() {
  const me = useMe();
  const client = useQueryClient();
  const signOut = useMutation({
    mutationFn: async () => unwrapEmpty(await api.POST("/api/auth/signout")),
    onSettled: () => {
      endSession(client, { deliberate: true });
      sendSessionSignal("signed-out");
    },
  });
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
      <Button type="button" small fill busy={signOut.isPending} onClick={() => signOut.mutate()}>
        Wyloguj się
      </Button>
    </div>
  );
}
