import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  Armchair,
  Bookmark,
  BookmarkCheck,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  ChartNoAxesColumn,
  FileText,
  Files,
  House,
  Info,
  LayoutGrid,
  type LucideIcon,
  LoaderCircle,
  Menu,
  Minus,
  Moon,
  Plus,
  RefreshCw,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  SquarePen,
  Sun,
  Table2,
  TriangleAlert,
  X,
} from "lucide-react";
import type { SVGProps } from "react";

/**
 * The renti icon set is lucide (one library, one stroke weight, one grid). Decorative by default (`aria-hidden`):
 * the control that holds an icon carries the accessible name, never the icon. The names are ours, so a screen asks
 * for "alert", not for a library component, and the set can change in one place.
 */
const ICONS = {
  home: House,
  search: Search,
  files: Files,
  market: ChartNoAxesColumn,
  interior: Armchair,
  edit: SquarePen,
  settings: SlidersHorizontal,
  bookmark: Bookmark,
  bookmarked: BookmarkCheck,
  legal: FileText,
  terms: Scale,
  shield: ShieldCheck,
  moon: Moon,
  sun: Sun,
  arrow: ArrowRight,
  close: X,
  menu: Menu,
  help: CircleHelp,
  alert: TriangleAlert,
  error: CircleAlert,
  info: Info,
  check: Check,
  plus: Plus,
  minus: Minus,
  success: CircleCheck,
  chevron: ChevronRight,
  chevronDown: ChevronDown,
  refresh: RefreshCw,
  loader: LoaderCircle,
  cards: LayoutGrid,
  table: Table2,
  sortNone: ArrowUpDown,
  sortAsc: ArrowUp,
  sortDesc: ArrowDown,
} as const satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

/** One stroke weight for every icon at every size (lucide's own default, also what the animated set draws). */
export const ICON_STROKE = 2;

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name" | "children" | "ref"> {
  readonly name: IconName;
  /** Pixel size. */
  readonly size?: number;
}

export function Icon({ name, size = 18, ...rest }: IconProps) {
  const Glyph = ICONS[name];
  return <Glyph size={size} strokeWidth={ICON_STROKE} aria-hidden="true" focusable="false" {...rest} />;
}
