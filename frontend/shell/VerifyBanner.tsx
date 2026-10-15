import { useMutation } from "@tanstack/react-query";

import { api, unwrapEmpty } from "../api/client";
import { Button } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { useMe } from "./session";

/**
 * A signed-in account whose address is not confirmed cannot start analyses (the API refuses with
 * `EMAIL_NOT_VERIFIED` where it matters). Say so, and offer a new link; the server decides whether one can be sent.
 */
export function VerifyBanner() {
  const me = useMe();
  const resend = useMutation({
    mutationFn: async () =>
      unwrapEmpty(await api.POST("/api/auth/register/resend", { body: { email: me.email } })),
  });
  if (me.email_verified) return null;
  return (
    <InlineNotice
      tone="warning"
      title="Potwierdź adres e-mail"
      live="status"
      actions={
        <Button type="button" small busy={resend.isPending} onClick={() => resend.mutate()}>
          Wyślij link ponownie
        </Button>
      }
    >
      {resend.isSuccess
        ? "Jeśli to możliwe, wysłaliśmy nowy link. Sprawdź skrzynkę i spam."
        : "Dopóki adres nie jest potwierdzony, nie możesz zlecać nowych analiz."}
    </InlineNotice>
  );
}
