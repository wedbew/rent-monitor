import { useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "../../api/errors";
import { PageHeading } from "../../shell/PageHeading";
import { useMe } from "../../shell/session";
import { InlineNotice } from "../../ui/Status";
import { Skeleton } from "../../ui/Skeleton";
import { BoardPanel } from "./BoardPanel";
import { BriefPanel } from "./BriefPanel";
import { CataloguePanel } from "./CataloguePanel";
import { ClosedBeta } from "./common";
import { GenerationsPanel } from "./GenerationsPanel";
import { projectKey, useGenerations, useProject, useStartGeneration } from "./hooks";
import styles from "./interior.module.css";
import { ItemsPanel } from "./ItemsPanel";
import { PhotoPanel } from "./PhotoPanel";
import { RevisionsPanel } from "./RevisionsPanel";
import { Button } from "../../ui/Button";
import { t } from "../../i18n";

/** A project id is a UUID; anything else is not a project (rules/frontend.md section 5: a path parameter is input). */
const PROJECT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function Workspace({ projectId }: { readonly projectId: string }) {
  const project = useProject(projectId);
  const generations = useGenerations(projectId);
  const start = useStartGeneration();
  // One key per click that reached the server unanswered: a retry of that click reuses it, so a lost answer can never
  // start (and pay for) a second operation. A definite answer ends the click; the next click is a new key.
  const key = useRef<{ revision: string; key: string } | null>(null);
  const client = useQueryClient();
  const me = useMe();

  if (project.isPending) {
    return (
      <div role="status" aria-label={t.interior.workspace.loading}>
        <Skeleton height="6rem" />
      </div>
    );
  }
  if (project.isError) {
    if (project.error instanceof ApiError && project.error.code === "FEATURE_NOT_IN_PLAN")
      return <ClosedBeta />;
    const gone = project.error instanceof ApiError && project.error.status === 404;
    return (
      <InlineNotice
        tone="danger"
        title={gone ? t.interior.workspace.notFound : t.interior.failed}
        live="alert"
        actions={
          gone ? undefined : (
            <Button type="button" small onClick={() => void project.refetch()}>
              {t.interior.reload}
            </Button>
          )
        }
      />
    );
  }
  const data = project.data;
  const off = start.error instanceof ApiError && start.error.code === "GENERATION_UNAVAILABLE";

  function generate(revisionId: string) {
    if (start.isPending) return;
    const same = key.current?.revision === revisionId ? key.current.key : null;
    const clickKey = same ?? crypto.randomUUID();
    key.current = { revision: revisionId, key: clickKey };
    start.mutate(
      { projectId, revisionId, key: clickKey },
      {
        onSuccess: () => (key.current = null),
        onError: (error) => {
          // A refusal is an answer: the next click is a new one. A lost answer keeps the key for the retry.
          if (error instanceof ApiError && error.status < 500) key.current = null;
          void client.invalidateQueries({ queryKey: projectKey(me.id, projectId) });
        },
      },
    );
  }

  return (
    <>
      <PageHeading
        title={data.name}
        eyebrow={t.interior.eyebrow}
        lead={t.interior.rooms[data.brief.room_type]}
      />
      <p>
        <Link className={styles["link"]} to="/app/interior">
          {t.interior.workspace.back}
        </Link>
      </p>
      <div className={styles["stack"]}>
        <PhotoPanel project={data} />
        <BriefPanel key={data.project_id} project={data} />
        <ItemsPanel project={data} />
        <CataloguePanel project={data} />
        <BoardPanel project={data} />
        <RevisionsPanel
          project={data}
          generate={generate}
          generating={
            start.isPending ||
            (generations.data ?? []).some((g) => g.state === "queued" || g.state === "running")
          }
          generationOff={off}
        />
        <GenerationsPanel
          project={data}
          generations={generations.data ?? []}
          start={generate}
          starting={start.isPending}
          startError={start.isError && !off ? start.error : null}
          off={off}
        />
      </div>
    </>
  );
}

/** The workspace of one project: every section works without the others, and a section that is blocked says why. */
export function ProjectPage() {
  const { projectId = "" } = useParams();
  if (!PROJECT_ID.test(projectId)) {
    return <InlineNotice tone="danger" title={t.interior.workspace.notFound} />;
  }
  return (
    <div className={styles["page"]}>
      <Workspace projectId={projectId} />
    </div>
  );
}
