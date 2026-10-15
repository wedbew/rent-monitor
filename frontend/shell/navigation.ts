import type { IconName } from "../ui/Icon";
import { t } from "../i18n";

/**
 * The single registry behind the desktop rail and the mobile sheet. A destination knows its own active rule, so a
 * nested route lights the right item (a report under `/app/analyses/:id` is "Moje analizy", `/app/analyses/new` is
 * "Nowa analiza") and no component derives "current" from a click.
 */
export type Availability = "ready" | "building" | "unavailable";

export interface Destination {
  readonly id: string;
  readonly label: string;
  readonly to: string;
  readonly icon: IconName;
  readonly availability: Availability;
  readonly isActive: (pathname: string) => boolean;
}

const under = (prefix: string) => (pathname: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

export const PRIMARY: readonly Destination[] = [
  {
    id: "dashboard",
    label: t.shell.destinations["dashboard"],
    to: "/app",
    icon: "home",
    availability: "building",
    isActive: (p) => p === "/app",
  },
  {
    id: "new-analysis",
    label: t.shell.destinations["new-analysis"],
    to: "/app/analyses/new",
    icon: "search",
    availability: "building",
    isActive: under("/app/analyses/new"),
  },
  {
    id: "analyses",
    label: t.shell.destinations["analyses"],
    to: "/app/analyses",
    icon: "files",
    availability: "building",
    isActive: (p) => under("/app/analyses")(p) && !under("/app/analyses/new")(p),
  },
  {
    id: "market",
    label: t.shell.destinations["market"],
    to: "/app/market",
    icon: "market",
    availability: "unavailable",
    isActive: under("/app/market"),
  },
  {
    id: "interior",
    label: t.shell.destinations["interior"],
    to: "/app/interior",
    icon: "interior",
    availability: "unavailable",
    isActive: under("/app/interior"),
  },
  {
    id: "listing",
    label: t.shell.destinations["listing"],
    to: "/app/listings/new",
    icon: "edit",
    availability: "unavailable",
    isActive: under("/app/listings"),
  },
  {
    id: "settings",
    label: t.shell.destinations["settings"],
    to: "/app/settings",
    icon: "settings",
    availability: "building",
    isActive: under("/app/settings"),
  },
];

export const LEGAL: readonly Destination[] = [
  {
    id: "terms",
    label: t.shell.destinations["terms"],
    to: "/terms",
    icon: "legal",
    availability: "building",
    isActive: under("/terms"),
  },
  {
    id: "privacy",
    label: t.shell.destinations["privacy"],
    to: "/privacy",
    icon: "shield",
    availability: "building",
    isActive: under("/privacy"),
  },
];

export const ALL_DESTINATIONS: readonly Destination[] = [...PRIMARY, ...LEGAL];

/** The destination the current path belongs to, if any (document title, context). */
export function destinationFor(pathname: string): Destination | undefined {
  return ALL_DESTINATIONS.find((d) => d.isActive(pathname));
}
