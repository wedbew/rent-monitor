import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { ApiError } from "../../api/errors";
import { formatCount, formatDate } from "../../api/format";
import { PageHeading } from "../../shell/PageHeading";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, useFormAttempt } from "../../ui/FormErrors";
import { Select } from "../../ui/Select";
import { InlineNotice } from "../../ui/Status";
import { Skeleton } from "../../ui/Skeleton";
import { ClosedBeta, FailureNotice } from "./common";
import { type ProjectSummary, useCreateProject, useDeleteProject, useProjects } from "./hooks";
import styles from "./interior.module.css";
import { t } from "../../i18n";

const ROOMS = ["living_room", "bedroom", "kitchen", "bathroom", "hallway", "office", "other"] as const;
export type Room = (typeof ROOMS)[number];
export const roomOptions = ROOMS.map((value) => ({ value, label: t.interior.rooms[value] }));
const NAME_ID = "interior-new-name";

/**
 * The list of design projects and the form that starts one. A project lives 30 days from creation (editing never
 * extends it), so every card says when it expires. A 403 means the person is outside the closed beta: that is a
 * state of this page with its own words, not an error screen.
 */
// LEGAL[images]: projects hold the person's room and item photos (RM-451)
// GDPR[personal-data]: names and photos written by the person; kept 30 days, removed with the account (RM-451)
export function InteriorPage() {
  const projects = useProjects();
  const create = useCreateProject();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [room, setRoom] = useState<Room>("living_room");
  const [nameError, setNameError] = useState<string | null>(null);
  const [attempt, markInvalid] = useFormAttempt();
  const [toDelete, setToDelete] = useState<ProjectSummary | null>(null);
  const remove = useDeleteProject();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (create.isPending) return;
    if (name.trim() === "") {
      setNameError(t.interior.create.nameMissing);
      markInvalid();
      return;
    }
    setNameError(null);
    create.mutate(
      { name: name.trim(), brief: { room_type: room, keep: [] } },
      {
        onSuccess: (project) => void navigate(`/app/interior/${project.project_id}`),
        onError: () => markInvalid(),
      },
    );
  }

  const denied =
    projects.error instanceof ApiError && projects.error.code === "FEATURE_NOT_IN_PLAN"
      ? projects.error
      : null;

  return (
    <div className={styles["page"]}>
      <PageHeading title={t.interior.title} eyebrow={t.interior.eyebrow} lead={t.interior.lead} />
      {denied !== null ? <ClosedBeta /> : null}
      {denied === null ? (
        <>
          <form className={styles["card"]} onSubmit={submit} noValidate>
            <h2 className={styles["h2"]}>{t.interior.create.title}</h2>
            <FormErrorSummary
              errors={nameError ? [{ fieldId: NAME_ID, message: nameError }] : []}
              attempt={attempt}
            />
            <TextField
              fieldId={NAME_ID}
              label={t.interior.create.name}
              hint={t.interior.create.nameHint}
              value={name}
              onValueChange={(next) => {
                setName(next);
                setNameError(null);
              }}
              error={nameError}
              maxLength={120}
              autoComplete="off"
            />
            <Select
              label={t.interior.create.room}
              value={room}
              options={roomOptions}
              onValueChange={(next) => setRoom(next as Room)}
            />
            {create.isError ? <FailureNotice error={create.error} /> : null}
            <div className={styles["actions"]}>
              <Button type="submit" variant="primary" busy={create.isPending}>
                {t.interior.create.submit}
              </Button>
            </div>
          </form>

          <section aria-labelledby="interior-projects" className={styles["stack"]}>
            <h2 className={styles["h2"]} id="interior-projects">
              {t.interior.list.label}
            </h2>
            <p className={styles["muted"]}>{t.interior.list.retention}</p>
            {projects.isPending ? (
              <div role="status" aria-label={t.interior.list.loading}>
                <Skeleton height="4rem" />
              </div>
            ) : projects.isError ? (
              <InlineNotice
                tone="danger"
                title={t.interior.failed}
                live="alert"
                actions={
                  <Button type="button" small onClick={() => void projects.refetch()}>
                    {t.interior.reload}
                  </Button>
                }
              />
            ) : projects.data.length === 0 ? (
              <div className={styles["empty"]}>
                <strong>{t.interior.list.emptyTitle}</strong>
                <p>{t.interior.list.emptyBody}</p>
              </div>
            ) : (
              <ul className={styles["cards"]}>
                {projects.data.map((project) => (
                  <li key={project.project_id} className={styles["card"]}>
                    <h3 className={styles["h3"]}>{project.name}</h3>
                    <p className={styles["muted"]}>{t.interior.rooms[project.room_type]}</p>
                    <ul className={styles["facts"]}>
                      <li>{project.has_source ? t.interior.list.hasPhoto : t.interior.list.noPhoto}</li>
                      <li>{t.interior.list.versions({ count: formatCount(project.revisions) })}</li>
                      <li>{t.interior.list.expires({ date: formatDate(project.expires_at) })}</li>
                    </ul>
                    <div className={styles["actions"]}>
                      <Link
                        className={styles["linkButton"]}
                        to={`/app/interior/${project.project_id}`}
                        aria-label={t.interior.list.open({ name: project.name })}
                      >
                        {t.interior.list.openShort}
                      </Link>
                      <Button
                        type="button"
                        variant="danger"
                        small
                        aria-label={t.interior.list.delete({ name: project.name })}
                        onClick={() => setToDelete(project)}
                      >
                        {t.interior.list.deleteShort}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}

      <Dialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={t.interior.list.deleteTitle}
        description={t.interior.list.deleteBody}
        variant="modal"
      >
        <div className={styles["actions"]}>
          <Button type="button" onClick={() => setToDelete(null)}>
            {t.interior.list.cancel}
          </Button>
          <Button
            type="button"
            variant="danger"
            busy={remove.isPending}
            onClick={() => {
              if (toDelete === null || remove.isPending) return;
              remove.mutate(
                { projectId: toDelete.project_id },
                {
                  onSuccess: () => setToDelete(null),
                },
              );
            }}
          >
            {t.interior.list.deleteConfirm}
          </Button>
        </div>
        {remove.isError ? <FailureNotice error={remove.error} /> : null}
      </Dialog>
    </div>
  );
}
