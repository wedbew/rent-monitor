export interface Pins {
  image: string;
  digest: string;
  playwright: string;
  node: string;
}
export function pinnedImage(): { image: string; version: string; digest: string };
export function playwrightVersion(): string;
export function nodeVersion(): string;
export const BASELINE_FILE: string;
export function recordedBaseline(): Pins | null;
export function currentPins(): Pins;
