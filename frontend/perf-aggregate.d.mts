export const PROJECTS: string[];
export const PAGES: string[];
export interface PerfArtifact {
  page: string;
  project: string;
  browserVersion: string;
  lcpMs: number | null;
  cls: number;
  slowestInteractionMs: number | null;
}
export function collect(dir: string): PerfArtifact[];
export function summarise(
  rows: PerfArtifact[],
  now?: Date,
): { rows: unknown[]; browserVersion: string; measuredAt: string };
