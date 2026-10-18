import { useState } from "react";
import { Link } from "react-router";

import { isAmbiguousFailure } from "../../api/errors";
import { formatCount, formatDateTime } from "../../api/format";
import { describeTransport } from "../../api/problems";
import { PageHeading } from "../../shell/PageHeading";
import { ThemeControl } from "../../shell/ThemeControl";
import { useMe } from "../../shell/session";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { newPasswordError, PASSWORD_MIN, readFailure } from "../auth/forms";
import { ProblemNotice } from "../auth/ProblemNotice";
import { orderSessions, type SessionRow } from "./sessions";
import {
  useChangePassword,
  useDeleteAccount,
  useExportData,
  useSessions,
  useSignOutEverywhere,
} from "./useSettings";
import styles from "./SettingsPage.module.css";
import { t } from "../../i18n";

/** The API's limit on `GET /api/me/export` (per hour); the copy says it so nobody is surprised by a 429. */
const EXPORT_LIMIT_PER_HOUR = 5;

/** What went wrong with a request, in the app's words: the stable copy, the retry time, the request id. */
function describeFailure(error: unknown) {
  return readFailure(error).general ?? describeTransport("invalid-response");
}

function Section({
  id,
  title,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly children: React.ReactNode;
}) {
  return (
    <section className={styles["section"]} aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

function ProfileSection() {
  const me = useMe();
  return (
    <Section id="settings-profile" title={t.settings.profile.heading}>
      <dl className={styles["facts"]} aria-label={t.settings.profile.list}>
        <div>
          <dt>{t.settings.profile.email}</dt>
          <dd>{me.email}</dd>
        </div>
        <div>
          <dt>{t.settings.profile.name}</dt>
          <dd>{me.name ?? t.settings.profile.noName}</dd>
        </div>
        <div>
          <dt>{t.settings.profile.status}</dt>
          <dd>{me.email_verified ? t.settings.profile.verified : t.settings.profile.unverified}</dd>
        </div>
      </dl>
    </Section>
  );
}

function AppearanceSection() {
  return (
    <Section id="settings-appearance" title={t.settings.appearance.heading}>
      <p className={styles["note"]}>{t.settings.appearance.body}</p>
      <div>
        <ThemeControl />
      </div>
    </Section>
  );
}

function SessionItem({ row }: { readonly row: SessionRow }) {
  return (
    <li className={styles["session"]}>
      <div className={styles["sessionHead"]}>
        <strong className={styles["device"]}>{row.userAgent ?? t.settings.sessions.unknownDevice}</strong>
        {row.current ? <span className={styles["badge"]}>{t.settings.sessions.current}</span> : null}
      </div>
      <span className={styles["meta"]}>{row.ip ?? t.settings.sessions.unknownIp}</span>
      <span className={styles["meta"]}>
        {t.settings.sessions.lastSeen({ when: formatDateTime(row.lastSeen) })}
        {" · "}
        {t.settings.sessions.expires({ when: formatDateTime(row.expiresAt) })}
      </span>
    </li>
  );
}

function SessionsSection() {
  const sessions = useSessions();
  const signOutAll = useSignOutEverywhere();
  const [open, setOpen] = useState(false);
  const failure = signOutAll.isError ? describeFailure(signOutAll.error) : null;
  const unknown = signOutAll.isError && isAmbiguousFailure(signOutAll.error);
  const pending = signOutAll.isPending;
  // Every door out of the dialog (Cancel, Escape, the backdrop, the close button) is shut while the request runs:
  // the operation belongs to the dialog until the server answered, and its state is never reset under it.
  const close = () => {
    if (!pending) setOpen(false);
  };

  return (
    <Section id="settings-sessions" title={t.settings.sessions.heading}>
      <p className={styles["note"]}>{t.settings.sessions.lead}</p>
      {sessions.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.settings.loading} className={styles["skeleton"]}>
          <Skeleton height="4rem" />
        </div>
      ) : sessions.isError ? (
        <InlineNotice
          tone="danger"
          title={t.settings.sessions.loadFailed}
          live="alert"
          actions={
            <Button type="button" icon="refresh" onClick={() => void sessions.refetch()}>
              {t.settings.sessions.retry}
            </Button>
          }
        />
      ) : sessions.data.length === 0 ? (
        <p className={styles["note"]}>{t.settings.sessions.empty}</p>
      ) : (
        <ul className={styles["sessions"]} aria-label={t.settings.sessions.list}>
          {orderSessions(sessions.data).map((row) => (
            <SessionItem key={row.id} row={row} />
          ))}
        </ul>
      )}
      <div>
        <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
          {t.settings.sessions.signOutAll}
        </Button>
      </div>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!pending) setOpen(next);
        }}
        onClosed={() => signOutAll.reset()}
        title={t.settings.sessions.confirmTitle}
        description={t.settings.sessions.confirmBody}
      >
        <div className={styles["dialogBody"]}>
          {unknown ? (
            <InlineNotice tone="warning" title={t.settings.unknown.title} live="alert">
              {t.settings.unknown.signOutAll}
            </InlineNotice>
          ) : failure ? (
            <InlineNotice tone="danger" title={failure.title} live="alert">
              {failure.detail}
            </InlineNotice>
          ) : null}
          <div className={styles["dialogActions"]}>
            <Button type="button" disabled={pending} onClick={close}>
              {t.settings.sessions.cancel}
            </Button>
            <Button
              type="button"
              variant="danger"
              busy={pending}
              onClick={() => {
                if (!pending) signOutAll.mutate();
              }}
            >
              {t.settings.sessions.confirm}
            </Button>
          </div>
        </div>
      </Dialog>
    </Section>
  );
}

const CURRENT_ID = "settings-password-current";
const NEXT_ID = "settings-password-new";

function NoPasswordSection() {
  return (
    <Section id="settings-password" title={t.settings.password.heading}>
      <InlineNotice tone="info" title={t.settings.password.noPasswordTitle}>
        {t.settings.password.noPasswordBody}{" "}
        <Link to="/password/forgot">{t.settings.password.noPasswordLink}</Link>
      </InlineNotice>
    </Section>
  );
}

/** The change form only for an account the API says has a password; nothing is inferred from how they signed in. */
function PasswordSection() {
  const me = useMe();
  return me.has_password ? <ChangePasswordSection /> : <NoPasswordSection />;
}

function ChangePasswordSection() {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [clientErrors, setClientErrors] = useState<readonly FieldError[]>([]);
  const [attempt, markInvalid] = useFormAttempt();

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (change.isPending) return;
    const found: FieldError[] = [];
    const currentProblem = current === "" ? t.settings.password.currentMissing : null;
    const nextProblem = newPasswordError(next);
    if (currentProblem) found.push({ fieldId: CURRENT_ID, message: currentProblem });
    if (nextProblem) found.push({ fieldId: NEXT_ID, message: nextProblem });
    setClientErrors(found);
    if (found.length > 0) {
      markInvalid();
      return;
    }
    change.mutate({ current_password: current, new_password: next }, { onError: markInvalid });
  };

  const failure = change.isError ? readFailure(change.error) : null;
  const serverErrors: FieldError[] = [];
  if (failure?.code === "INVALID_CREDENTIALS")
    serverErrors.push({ fieldId: CURRENT_ID, message: t.settings.password.wrongCurrent });
  if (failure?.fields["current_password"])
    serverErrors.push({ fieldId: CURRENT_ID, message: failure.fields["current_password"] });
  const nextServer = failure?.fields["password"] ?? failure?.fields["new_password"];
  if (nextServer) serverErrors.push({ fieldId: NEXT_ID, message: nextServer });
  const shown = clientErrors.length > 0 ? clientErrors : serverErrors;
  const messageFor = (fieldId: string) => shown.find((e) => e.fieldId === fieldId)?.message ?? null;
  const unknown = change.isError && isAmbiguousFailure(change.error);
  const general = failure?.code === "INVALID_CREDENTIALS" || unknown ? null : (failure?.general ?? null);

  return (
    <Section id="settings-password" title={t.settings.password.heading}>
      <p className={styles["note"]}>{t.settings.password.lead}</p>
      <form className={styles["form"]} onSubmit={submit} noValidate aria-label={t.settings.password.form}>
        <FormErrorSummary errors={shown} attempt={attempt} />
        {unknown ? (
          <InlineNotice tone="warning" title={t.settings.unknown.title} live="alert">
            {t.settings.unknown.password}
          </InlineNotice>
        ) : null}
        {general ? <ProblemNotice key={attempt} problem={general} /> : null}
        <TextField
          fieldId={CURRENT_ID}
          label={t.settings.password.current}
          type="password"
          name="current-password"
          autoComplete="current-password"
          value={current}
          onValueChange={(value) => {
            setCurrent(value);
            setClientErrors([]);
          }}
          error={messageFor(CURRENT_ID)}
        />
        <TextField
          fieldId={NEXT_ID}
          label={t.settings.password.next}
          type="password"
          name="new-password"
          autoComplete="new-password"
          hint={t.settings.password.hint({ min: formatCount(PASSWORD_MIN) })}
          value={next}
          onValueChange={(value) => {
            setNext(value);
            setClientErrors([]);
          }}
          error={messageFor(NEXT_ID)}
        />
        <div>
          <Button type="submit" variant="primary" busy={change.isPending}>
            {t.settings.password.submit}
          </Button>
        </div>
      </form>
    </Section>
  );
}

function DataSection() {
  const exported = useExportData();
  const failure = exported.isError ? describeFailure(exported.error) : null;
  return (
    <Section id="settings-data" title={t.settings.data.heading}>
      <p className={styles["note"]}>{t.settings.data.lead({ limit: formatCount(EXPORT_LIMIT_PER_HOUR) })}</p>
      {failure ? <ProblemNotice problem={failure} /> : null}
      {exported.isSuccess ? (
        <InlineNotice tone="success" title={t.settings.data.exportDone} live="status" />
      ) : null}
      <div>
        <Button
          type="button"
          busy={exported.isPending}
          onClick={() => {
            if (!exported.isPending) exported.mutate();
          }}
        >
          {t.settings.data.export}
        </Button>
      </div>
    </Section>
  );
}

const CONFIRM_ID = "settings-erase-email";

function EraseSection() {
  const me = useMe();
  const erase = useDeleteAccount();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [attempt, markInvalid] = useFormAttempt();

  const failure = erase.isError ? readFailure(erase.error) : null;
  const mismatch = failure?.code === "CONFIRMATION_MISMATCH" ? t.settings.erase.mismatch : null;
  const message = clientError ?? mismatch ?? failure?.fields["confirm_email"] ?? null;
  const shown: FieldError[] = message ? [{ fieldId: CONFIRM_ID, message }] : [];
  const unknown = erase.isError && isAmbiguousFailure(erase.error);
  const general = mismatch || unknown ? null : (failure?.general ?? null);
  const pending = erase.isPending;
  // Every door out of the dialog is shut while the request runs (see the sessions dialog).
  const close = () => {
    if (!pending) setOpen(false);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (erase.isPending) return;
    if (typed.trim().toLowerCase() !== me.email.trim().toLowerCase()) {
      setClientError(t.settings.erase.mismatch);
      markInvalid();
      return;
    }
    setClientError(null);
    erase.mutate(typed.trim(), { onError: markInvalid });
  };

  return (
    <Section id="settings-erase" title={t.settings.erase.heading}>
      <p className={styles["note"]}>{t.settings.erase.lead}</p>
      <div>
        <Button type="button" variant="danger" onClick={() => setOpen(true)}>
          {t.settings.erase.open}
        </Button>
      </div>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!pending) setOpen(next);
        }}
        onClosed={() => {
          erase.reset();
          setTyped("");
          setClientError(null);
        }}
        title={t.settings.erase.title}
        description={t.settings.erase.body}
      >
        <form className={styles["dialogBody"]} onSubmit={submit} noValidate>
          <FormErrorSummary errors={shown} attempt={attempt} />
          {unknown ? (
            <InlineNotice tone="warning" title={t.settings.unknown.title} live="alert">
              {t.settings.unknown.erase}
            </InlineNotice>
          ) : null}
          {general ? <ProblemNotice key={attempt} problem={general} /> : null}
          <TextField
            fieldId={CONFIRM_ID}
            label={t.settings.erase.confirmField}
            type="email"
            name="confirm-email"
            autoComplete="off"
            inputMode="email"
            value={typed}
            onValueChange={(value) => {
              setTyped(value);
              setClientError(null);
            }}
            error={message}
          />
          <div className={styles["dialogActions"]}>
            <Button type="button" disabled={pending} onClick={close}>
              {t.settings.erase.cancel}
            </Button>
            <Button type="submit" variant="danger" busy={erase.isPending}>
              {t.settings.erase.submit}
            </Button>
          </div>
        </form>
      </Dialog>
    </Section>
  );
}

/**
 * `/app/settings` (RM-278): profile, appearance, signed-in browsers, password, data export and account erasure,
 * every one backed by an API that exists. Requests that end the session go through `endSession` (rules/frontend.md
 * section 3); the export is saved as a file and never kept in memory.
 */
// GDPR[personal-data]: shows the account's e-mail and name and the sessions' IP address and user agent, to their owner only (RM-278)
// GDPR[erasure]: account deletion requires typing the account's own e-mail; the API erases and signs out (RM-278)
export function SettingsPage() {
  return (
    <div className={styles["page"]}>
      <PageHeading title={t.settings.title} lead={t.settings.lead} />
      <ProfileSection />
      <AppearanceSection />
      <SessionsSection />
      <PasswordSection />
      <DataSection />
      <EraseSection />
    </div>
  );
}
