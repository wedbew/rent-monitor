import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";

import { api, unwrap, unwrapEmpty } from "../../api/client";
import { safeNext, startSession } from "../../shell/session";

/** Where to go once signed in: the page the person was sent from, or the dashboard. Never another origin. */
export function useNextPath(): string {
  const [params] = useSearchParams();
  return safeNext(params.get("next"));
}

function useStartAndGo() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const next = useNextPath();
  return (me: Parameters<typeof startSession>[1]) => {
    startSession(client, me);
    void navigate(next, { replace: true });
  };
}

/** Mutations are never retried (api/query.ts): a sign-in attempt or a sent mail must not be repeated by a library. */
export function useLogin() {
  const done = useStartAndGo();
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      unwrap(await api.POST("/api/auth/login", { body })),
    onSuccess: done,
  });
}

export function useGoogleSignIn() {
  const done = useStartAndGo();
  return useMutation({
    mutationFn: async (credential: string) =>
      unwrap(await api.POST("/api/auth/google", { body: { credential } })),
    onSuccess: done,
  });
}

export function useMagicLinkRequest() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrapEmpty(await api.POST("/api/auth/email/start", { body: { email } })),
  });
}

export function useMagicLinkVerify() {
  const done = useStartAndGo();
  return useMutation({
    mutationFn: async (token: string) =>
      unwrap(await api.POST("/api/auth/email/verify", { body: { token } })),
    onSuccess: done,
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      unwrapEmpty(await api.POST("/api/auth/register", { body })),
  });
}

export function useRegisterResend() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrapEmpty(await api.POST("/api/auth/register/resend", { body: { email } })),
  });
}

export function useRegisterVerify() {
  const done = useStartAndGo();
  return useMutation({
    mutationFn: async (token: string) =>
      unwrap(await api.POST("/api/auth/register/verify", { body: { token } })),
    onSuccess: done,
  });
}

export function usePasswordForgot() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrapEmpty(await api.POST("/api/auth/password/forgot", { body: { email } })),
  });
}

export function usePasswordReset() {
  return useMutation({
    mutationFn: async (body: { token: string; password: string }) =>
      unwrapEmpty(await api.POST("/api/auth/password/reset", { body })),
  });
}
