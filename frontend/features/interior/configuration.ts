/** Product defaults for the guided workspace. Custom styles are always available alongside these suggestions. */
export const interiorConfiguration = {
  initialStep: "photo",
  initialView: "guided",
  steps: ["photo", "brief", "furniture", "review"],
  stylePresets: [
    "natural",
    "minimal",
    "warm",
    "loft",
    "scandinavian",
    "japandi",
    "modern",
    "classic",
    "boho",
    "artDeco",
  ],
} as const;

export type InteriorStep = (typeof interiorConfiguration.steps)[number];
