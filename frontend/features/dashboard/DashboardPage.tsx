import { Link } from "react-router";

import { formatDate, formatMoney, formatReports } from "../../api/format";
import { describeProblem, describeTransport } from "../../api/problems";
import { ApiError, TransportError } from "../../api/errors";
import { PageHeading } from "../../shell/PageHeading";
import { type Me, useMe } from "../../shell/session";
import { Button, LinkButton } from "../../ui/Button";
import { Icon, type IconName } from "../../ui/Icon";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { retryIn } from "../auth/forms";
import { type AuditSummary, useRecentAudits } from "../analyses/queries";
import { statusCopy } from "../analyses/status";
import styles from "./DashboardPage.module.css";
import { t } from "../../i18n";

interface Tool {
  readonly id: string;
  readonly number: string;
  readonly icon: IconName;
  readonly title: string;
  readonly body: string;
  readonly cta: string;
  readonly to: string;
  /** Is the feature built end to end? Only then is there something to link to. */
  readonly built: boolean;
  /** Feature flag (GET /api/me `flags`) that may switch a built tool off; absent flag = on. */
  readonly flag?: string;
}

const TOOLS: readonly Tool[] = [
  {
    id: "analysis",
    number: "01",
    icon: "search",
    ...t.dashboard.tools["analysis"],
    to: "/app/analyses/new",
    built: true,
  },
  {
    id: "interior",
    number: "02",
    icon: "interior",
    ...t.dashboard.tools["interior"],
    to: "/app/interior",
    built: false,
    flag: "interior",
  },
  {
    id: "listing",
    number: "03",
    icon: "edit",
    ...t.dashboard.tools["listing"],
    to: "/app/listings/new",
    built: false,
    flag: "listing",
  },
];

export function toolIsAvailable(tool: Tool, flags: Readonly<Record<string, boolean>>): boolean {
  if (!tool.built) return false;
  return tool.flag === undefined || flags[tool.flag] !== false;
}

function ToolCard({ tool, me }: { readonly tool: Tool; readonly me: Me }) {
  const available = toolIsAvailable(tool, me.flags);
  const breaker = tool.id === "analysis" && me.upstream.otodom_breaker_open;
  return (
    <article className={styles["tool"]}>
      <div className={styles["toolTop"]}>
        <Icon name={tool.icon} size={24} />
        <span aria-hidden="true">{tool.number}</span>
      </div>
      <h2>{tool.title}</h2>
      <p>{tool.body}</p>
      {!available ? (
        <span className={styles["soon"]}>{t.common.soon}</span>
      ) : breaker ? (
        <span className={styles["soon"]}>{t.dashboard.tools.temporarilyUnavailable}</span>
      ) : (
        <LinkButton to={tool.to} icon="arrow">
          {tool.cta}
        </LinkButton>
      )}
    </article>
  );
}

function rowTitle(audit: AuditSummary): string {
  return t.common.listingTitle({ id: audit.otodom_id });
}

function RecentRow({ audit }: { readonly audit: AuditSummary }) {
  const copy = statusCopy(audit.status, audit.error_code);
  const meta = [
    formatDate(audit.created_at),
    audit.grade !== null ? t.dashboard.recent.grade({ grade: audit.grade }) : null,
    audit.asking_price_pln !== null
      ? t.dashboard.recent.askingPrice({ price: formatMoney(audit.asking_price_pln, { decimals: 0 }) })
      : null,
  ].filter(Boolean);
  return (
    <li className={styles["row"]}>
      <Link to={`/app/analyses/${audit.audit_id}`} className={styles["rowLink"]}>
        <span>
          <span className={styles["rowTitle"]}>{rowTitle(audit)}</span>
          <span className={styles["rowMeta"]}>{meta.join(" · ")}</span>
        </span>
        <span className={`${styles["badge"]} ${styles[copy.tone]}`}>{copy.label}</span>
      </Link>
    </li>
  );
}

function Recent() {
  const recent = useRecentAudits(5);
  if (recent.isPending) {
    return (
      <div
        className={styles["skeletons"]}
        role="status"
        aria-busy="true"
        aria-label={t.dashboard.recent.loading}
      >
        <Skeleton height="56px" />
        <Skeleton height="56px" />
        <Skeleton height="56px" />
      </div>
    );
  }
  if (recent.isError) {
    const failure =
      recent.error instanceof ApiError && recent.error.code !== null
        ? describeProblem(recent.error.code, { requestId: recent.error.requestId })
        : describeTransport(recent.error instanceof TransportError ? recent.error.kind : "invalid-response");
    return (
      <InlineNotice
        tone="danger"
        title={t.dashboard.recent.failed}
        live="alert"
        actions={
          <Button
            type="button"
            variant="primary"
            icon="refresh"
            busy={recent.isFetching}
            onClick={() => void recent.refetch()}
          >
            {t.common.retry}
          </Button>
        }
      >
        {failure.detail}
      </InlineNotice>
    );
  }
  if (recent.data.items.length === 0) {
    return (
      <div className={styles["empty"]}>
        <strong>{t.dashboard.recent.emptyTitle}</strong>
        <p>{t.dashboard.recent.emptyBody}</p>
        <div>
          <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
            {t.dashboard.recent.emptyAction}
          </LinkButton>
        </div>
      </div>
    );
  }
  return (
    <ul className={styles["list"]} aria-label={t.dashboard.recent.label}>
      {recent.data.items.map((audit) => (
        <RecentRow key={audit.audit_id} audit={audit} />
      ))}
    </ul>
  );
}

/**
 * The dashboard for the whole app: what you can do, how many reports you have (from the server, never counted
 * here), and your latest analyses. It shows nothing that does not exist: tools that are not built say "Wkrótce",
 * and the activity list is the real one, empty on a first visit.
 */
export function DashboardPage() {
  const me = useMe();
  const breaker = me.upstream.otodom_breaker_open;
  const first = (me.name ?? "").trim().split(/\s+/)[0] ?? "";
  return (
    <div className={styles["page"]}>
      <PageHeading
        title={t.dashboard.title}
        eyebrow={t.dashboard.eyebrow}
        lead={first ? t.dashboard.greetingLead({ name: first }) : t.dashboard.lead}
      />

      {breaker ? (
        <InlineNotice tone="warning" title={t.common.otodomLimited.title} live="status">
          {t.common.otodomLimited.paused({ when: retryIn(me.upstream.retry_after_s) })}
        </InlineNotice>
      ) : null}

      <section className={styles["tools"]} aria-label={t.dashboard.tools.label}>
        {TOOLS.map((tool) => (
          <ToolCard key={tool.id} tool={tool} me={me} />
        ))}
      </section>

      <section className={styles["lower"]}>
        <div>
          <div className={styles["heading"]}>
            <div>
              <p className={styles["eyebrow"]}>{t.dashboard.recent.eyebrow}</p>
              <h2>{t.dashboard.recent.heading}</h2>
            </div>
            <Link to="/app/analyses" className={styles["textLink"]}>
              {t.shell.destinations.analyses}
              <Icon name="arrow" />
            </Link>
          </div>
          <Recent />
        </div>
        <aside className={styles["side"]} aria-label={t.dashboard.side.label}>
          <div className={styles["credit"]}>
            <p className={styles["eyebrow"]}>{t.dashboard.side.reportsEyebrow}</p>
            <strong>{formatReports(me.credit_balance)}</strong>
            <span>{t.dashboard.side.reportsNote}</span>
            {me.credit_balance === 0 ? (
              <LinkButton to="/app/credits" variant="primary" icon="arrow">
                {t.common.buyReports}
              </LinkButton>
            ) : null}
          </div>
          <div>
            <p className={styles["eyebrow"]}>{t.dashboard.side.marketEyebrow}</p>
            <h2 className={styles["marketTitle"]}>{t.dashboard.side.marketTitle}</h2>
            <p className={styles["soonText"]}>{t.dashboard.side.marketBody}</p>
            <LinkButton to="/app/market" icon="arrow">
              {t.dashboard.side.marketAction}
            </LinkButton>
          </div>
        </aside>
      </section>
    </div>
  );
}
