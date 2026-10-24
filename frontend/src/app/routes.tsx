import type { ReactNode } from "react";
import { annotateFeature } from "@/features/annotate";
import { calibrationFeature } from "@/features/calibration";
import { catalogFeature } from "@/features/catalog";
import { compareFeature } from "@/features/compare";
import { dataSourcesFeature } from "@/features/data-sources";
import { datasetsFeature } from "@/features/datasets";
import { experimentsFeature } from "@/features/experiments";
import { playgroundFeature } from "@/features/playground";
import { resultsFeature } from "@/features/results";
import { transcriptsFeature } from "@/features/transcripts";

export interface Feature {
  /** sidebar entry; omit for pages reachable only by link (e.g. a trial) */
  nav?: { label: string; to: string; group: string };
  routes: { path: string; element: ReactNode }[];
}

/** To add a page: create features/<name>/index.tsx exporting a Feature and list it here. */
export const features: Feature[] = [
  playgroundFeature, catalogFeature, datasetsFeature, dataSourcesFeature,
  experimentsFeature, resultsFeature, transcriptsFeature, compareFeature, annotateFeature, calibrationFeature,
];
