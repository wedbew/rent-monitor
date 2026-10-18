import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { tenantKey } from "../../api/query";
import { useMe } from "../../shell/session";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";
import type { Intent } from "./intent";
import type { Purchase } from "./guards";
import { useIntentLookup } from "./queries";

export interface Recovery {
  /** What the server said about the unresolved purchase: that order, or nothing. `null` until it answered. */
  readonly outcome: { readonly found: Purchase | null } | null;
  readonly clearOutcome: () => void;
  readonly checking: boolean;
  readonly failed: boolean;
  /** Ask the server about the unresolved purchase now (the person's own action). */
  readonly check: () => void;
}

/**
 * Settles an unresolved checkout with the server: the purchase created with exactly that request key, found or not
 * found. It runs on its own once when the page opens with an unresolved purchase (a reload or a return), and again
 * when the person asks. A late answer from an earlier session settles nothing. Reading creates no order.
 */
export function useIntentRecovery(intent: Intent | null, resolve: () => void, park: () => void): Recovery {
  const client = useQueryClient();
  const me = useMe();
  const lookup = useIntentLookup();
  const { mutate } = lookup;
  const [outcome, setOutcome] = useState<Recovery["outcome"]>(null);
  const [initial] = useState(intent);

  const run = useCallback(
    (target: Intent) => {
      const started = sessionGeneration();
      mutate(target, {
        onSuccess: (found) => {
          if (!isCurrentSession(started)) return;
          setOutcome({ found: found[0] ?? null }); // one request key: zero or one purchase
          if (found.length === 0) {
            park(); // "not found" is not proof it will never arrive: the key stays for the same pack
            return;
          }
          resolve();
          void client.invalidateQueries({ queryKey: tenantKey(me.id, "billing", "purchases") });
        },
      });
    },
    [mutate, resolve, park, client, me.id],
  );

  useEffect(() => {
    if (initial !== null && initial.parked !== true) run(initial);
  }, [initial, run]);

  return {
    outcome,
    clearOutcome: () => setOutcome(null),
    checking: lookup.isPending,
    failed: lookup.isError,
    check: () => {
      if (intent !== null && !lookup.isPending) run(intent);
    },
  };
}
