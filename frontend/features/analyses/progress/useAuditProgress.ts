import { useEffect, useState } from "react";

import { type Frame, isTerminal } from "./frames";
import { type Connection, watch } from "./streams";

export interface Progress {
  readonly connection: Connection;
  /** Stages seen so far, in the order the server reported them (never a list of what is "still to come"). */
  readonly stages: readonly string[];
  readonly stage: string | null;
  readonly pct: number | null;
  readonly terminal: Frame | null;
}

const START: Progress = { connection: "connecting", stages: [], stage: null, pct: null, terminal: null };

/**
 * What the server says about a running analysis. Stage and percentage are only ever copied from its frames; a
 * terminal frame is reported once and the caller then re-reads the audit (the stream is a hint, the API is the truth).
 */
export interface ProgressHandlers {
  readonly onTerminal: (frame: Frame) => void;
  readonly onConnection?: (state: Connection) => void;
}

export function useAuditProgress(eventsUrl: string | null, handlers: ProgressHandlers): Progress {
  const [progress, setProgress] = useState<Progress>(START);
  useEffect(() => {
    if (eventsUrl === null) return undefined;
    return watch(eventsUrl, {
      connection: (connection) => {
        handlers.onConnection?.(connection);
        setProgress((p) => (p.terminal ? p : { ...p, connection }));
      },
      frame: (frame) => {
        setProgress((p) => {
          if (p.terminal !== null) return p;
          if (isTerminal(frame)) return { ...p, connection: "live", terminal: frame };
          const stages =
            frame.stage !== null && !p.stages.includes(frame.stage) ? [...p.stages, frame.stage] : p.stages;
          return { ...p, stages, stage: frame.stage ?? p.stage, pct: frame.pct ?? p.pct };
        });
        if (isTerminal(frame)) handlers.onTerminal(frame);
      },
    });
    // The callback is read at delivery time; resubscribing on every render would reopen nothing but is wasted work.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- eventsUrl is the only identity that matters
  }, [eventsUrl]);
  return progress;
}
