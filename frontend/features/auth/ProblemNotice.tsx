import type { DescribedProblem } from "../../api/problems";
import { InlineNotice } from "../../ui/Status";
import { retryIn } from "./forms";
import styles from "./auth.module.css";
import { t } from "../../i18n";

interface ProblemNoticeProps {
  readonly problem: DescribedProblem;
  readonly tone?: "danger" | "warning" | "info";
  readonly actions?: React.ReactNode;
}

/** A failed request in words: the stable Polish copy, the retry time when throttled, the request id for support. */
export function ProblemNotice({ problem, tone = "danger", actions }: ProblemNoticeProps) {
  return (
    <InlineNotice tone={tone} title={problem.title} live="alert" {...(actions ? { actions } : {})}>
      {problem.detail}
      {problem.retryAfterS !== null ? t.auth.retry.tryAgain({ when: retryIn(problem.retryAfterS) }) : ""}
      {problem.requestId !== null ? (
        <span className={styles["support"]}>
          {" "}
          {t.auth.supportNumber} <code>{problem.requestId}</code>
        </span>
      ) : null}
    </InlineNotice>
  );
}
