import type { SVGProps } from "react";

/**
 * The renti icon set: 24 px outlines drawn with the current text colour. Decorative by default (`aria-hidden`):
 * the control that holds an icon carries the accessible name, never the icon.
 */
const PATHS = {
  home: "m3 10 9-7 9 7v10H3Z M9 20v-7h6v7",
  search: "M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12Z m5 11 6 6 M10 7v6 M7 10h6",
  files: "M6 3h9l4 4v14H6Z M15 3v5h4 M9 12h7 M9 16h5",
  market: "M3 20h18 M5 16v-5 M11 16V7 M17 16V3",
  interior: "M5 12V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v5 M5 10H3v9h18v-9h-2v5H5Z M5 19v2 M19 19v2",
  edit: "M13 4H4v17h16v-9 M10 14l1-4 8-8 3 3-8 8Z M17 4l3 3",
  settings: "M4 7h16 M4 17h16 M9 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z M15 14a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  legal: "M6 3h9l4 4v14H6Z M15 3v5h4 M9 12h7 M9 16h5",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z M9 12l2 2 4-4",
  moon: "M20.8 13.2A9 9 0 0 1 10.8 3.2a9 9 0 1 0 10 10Z",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5 19 19 M5 19l1.5-1.5 M17.5 6.5 19 5",
  arrow: "M4 12h15 M13 6l6 6-6 6",
  close: "m6 6 12 12 M6 18 18 6",
  menu: "M4 7h16 M4 12h16 M4 17h16",
  help: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5 M12 17v1",
  alert: "m12 3 10 18H2Z M12 9v5 M12 17v1",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z M12 10v7 M12 6v1",
  check: "m5 12 4 4L19 6",
  chevron: "m9 5 7 7-7 7",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7 M20 4v7h-7",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name" | "children"> {
  readonly name: IconName;
  /** Pixel size; the stroke stays 1.6 at every size. */
  readonly size?: number;
}

export function Icon({ name, size = 18, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
