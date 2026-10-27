import { useRef, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { ArrowLeft, ArrowRight, SlidersHorizontal } from "lucide-react";

import { formatCount, formatMoney } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { interiorConfiguration, type InteriorStep } from "./configuration";
import type { ProjectOut } from "./hooks";
import styles from "./interior.module.css";

export function ProjectWizard({
  project,
  dirty,
  children,
}: {
  readonly project: ProjectOut;
  readonly dirty: boolean;
  readonly children: Record<InteriorStep, ReactNode>;
}) {
  const [params, setParams] = useSearchParams();
  const step =
    interiorConfiguration.steps.find((value) => value === params.get("step")) ??
    interiorConfiguration.initialStep;
  const view =
    params.get("tools") === "all"
      ? "all"
      : params.get("tools") === "guided"
        ? "guided"
        : interiorConfiguration.initialView;
  function setView(next: "guided" | "all") {
    setParams(
      (previous) => {
        const updated = new URLSearchParams(previous);
        updated.set("tools", next);
        return updated;
      },
      { replace: true },
    );
  }
  const heading = useRef<HTMLHeadingElement>(null);
  const steps = interiorConfiguration.steps;
  const index = steps.indexOf(step);
  const copy = t.interior.wizard;

  function go(next: InteriorStep) {
    setParams(
      (previous) => {
        const updated = new URLSearchParams(previous);
        updated.set("step", next);
        updated.set("tools", "guided");
        return updated;
      },
      { replace: true },
    );
    // The heading stays mounted, so keyboard users arrive at a stable landmark after changing steps.
    heading.current?.focus();
  }

  return (
    <div className={styles["studio"]}>
      <aside className={styles["studioRail"]}>
        <h2 className={styles["railTitle"]}>{copy.navigation}</h2>
        <nav aria-label={copy.navigation}>
          <ol className={styles["steps"]}>
            {steps.map((value, i) => {
              return (
                <li key={value}>
                  <button
                    type="button"
                    className={styles["step"]}
                    aria-current={view === "guided" && value === step ? "step" : undefined}
                    onClick={() => {
                      go(value);
                    }}
                  >
                    <span className={styles["stepIcon"]} aria-hidden="true">
                      {formatCount(i + 1)}
                    </span>
                    <span className={styles["stepLabel"]}>{copy.number({ number: formatCount(i + 1) })}</span>
                    <span className={styles["stepCopy"]}>
                      <strong className={styles["stepTitle"]}>{copy.steps[value].title}</strong>
                      <strong className={styles["stepShortTitle"]}>{copy.steps[value].shortTitle}</strong>
                      <span>{copy.steps[value].hint}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
        <dl className={styles["projectFacts"]}>
          <div>
            <dt>{copy.room}</dt>
            <dd>{t.interior.rooms[project.brief.room_type]}</dd>
          </div>
          <div>
            <dt>{copy.style}</dt>
            <dd>{project.brief.style || copy.unspecified}</dd>
          </div>
          <div>
            <dt>{t.interior.brief.budget}</dt>
            <dd>
              {project.brief.budget_pln == null ? copy.unspecified : formatMoney(project.brief.budget_pln)}
            </dd>
          </div>
        </dl>
        <button
          type="button"
          className={styles["viewToggle"]}
          aria-pressed={view === "all"}
          onClick={() => setView(view === "all" ? "guided" : "all")}
        >
          <SlidersHorizontal size={16} aria-hidden="true" />
          {copy.allTools}
        </button>
        <p className={styles["muted"]}>{copy.viewHint}</p>
      </aside>
      <div className={styles["studioContent"]}>
        <header className={styles["stepHeading"]}>
          <p className={styles["eyebrow"]}>
            {view === "all"
              ? copy.allTools
              : copy.progress({ current: formatCount(index + 1), total: formatCount(steps.length) })}
          </p>
          <h2 ref={heading} tabIndex={-1}>
            {view === "all" ? copy.title : copy.steps[step].heading}
          </h2>
          <p className={styles["muted"]}>{view === "all" ? copy.allHint : copy.steps[step].description}</p>
        </header>
        {dirty ? (
          <p className={styles["draftNotice"]} role="status">
            {copy.unsaved}
          </p>
        ) : null}
        {steps.map((value) => (
          <div key={value} hidden={view !== "all" && step !== value}>
            <div className={styles["stack"]}>{children[value]}</div>
          </div>
        ))}
        {view === "guided" ? (
          <footer className={styles["wizardFooter"]}>
            <Button
              type="button"
              disabled={index === 0}
              onClick={() => {
                const previous = steps[index - 1];
                if (previous) go(previous);
              }}
            >
              <ArrowLeft size={16} aria-hidden="true" />
              {copy.previous}
            </Button>
            {index < steps.length - 1 ? (
              <Button
                type="button"
                variant="primary"
                disabled={step === "brief" && dirty}
                onClick={() => {
                  const next = steps[index + 1];
                  if (next) go(next);
                }}
              >
                {step === "furniture" ? copy.review : copy.next}
                <ArrowRight size={16} aria-hidden="true" />
              </Button>
            ) : (
              <p className={styles["muted"]}>{copy.finishHint}</p>
            )}
          </footer>
        ) : null}
      </div>
    </div>
  );
}
