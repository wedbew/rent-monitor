import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap, unwrapEmpty } from "../../api/client";
import { isAmbiguousFailure, TransportError } from "../../api/errors";
import { tenantKey } from "../../api/query";
import { whileSignedIn } from "../../shell/cancellable";
import { endSession, recheckSession, useMe } from "../../shell/session";
import { sendSessionSignal } from "../../shell/sessionBus";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";
import { saveJsonFile } from "./download";
import { readSessions, type SessionRow } from "./sessions";
import { t } from "../../i18n";

/** Sessions are asked again on every visit: a device signed in elsewhere must show up. */
export function useSessions() {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "settings", "sessions"),
    queryFn: async ({ signal }): Promise<readonly SessionRow[]> => {
      const rows = readSessions(unwrap(await api.GET("/api/auth/sessions", { signal })));
      if (rows === null) throw new TransportError("invalid-response");
      return rows;
    },
    staleTime: 0,
    refetchOnMount: "always",
  });
}

/**
 * A request that ends this person's sessions on the server (sign out everywhere, password change, deletion). On
 * success this tab goes through the one sign-out door (`endSession`), unless the session already ended or changed
 * while the request was in flight: then a different person may be signed in, and nothing here may touch them.
 */
function useEndsSession<V>(request: (variables: V, signal: AbortSignal) => Promise<void>) {
  const client = useQueryClient();
  return useMutation<void, Error, V, number>({
    mutationFn: (variables) => whileSignedIn((signal) => request(variables, signal)),
    onMutate: () => sessionGeneration(),
    onSuccess: (_data, _variables, started) => {
      if (!isCurrentSession(started)) return;
      endSession(client, { deliberate: true });
      sendSessionSignal("signed-out");
    },
    // The request may have been applied and the answer lost: ask the server whether this session still exists
    // instead of assuming either way. If it is gone, the session query takes the one sign-out door.
    onError: (error, _variables, started) => {
      if (started !== undefined && isCurrentSession(started) && isAmbiguousFailure(error))
        recheckSession(client);
    },
  });
}

export function useSignOutEverywhere() {
  return useEndsSession<void>(async (_variables, signal) =>
    unwrapEmpty(await api.POST("/api/auth/signout-all", { signal })),
  );
}

export function useChangePassword() {
  return useEndsSession<{ current_password: string; new_password: string }>(async (body, signal) =>
    unwrapEmpty(await api.POST("/api/auth/password/change", { body, signal })),
  );
}

export function useDeleteAccount() {
  return useEndsSession<string>(async (confirmEmail, signal) =>
    unwrapEmpty(await api.DELETE("/api/me", { body: { confirm_email: confirmEmail }, signal })),
  );
}

/**
 * Download the export. The document is saved as a file and dropped; it is never kept in the cache or in state. An
 * answer that comes back after the session ended is discarded: it belongs to the person who left.
 */
export function useExportData() {
  return useMutation({
    mutationFn: async (): Promise<void> => {
      const started = sessionGeneration();
      const data = await whileSignedIn(async (signal) => unwrap(await api.GET("/api/me/export", { signal })));
      if (!isCurrentSession(started)) return;
      saveJsonFile(t.settings.data.fileName({ date: new Date().toISOString().slice(0, 10) }), data);
    },
  });
}
