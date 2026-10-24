import type { Feature } from "@/app/routes";
import { Compare } from "./Compare";

export const compareFeature: Feature = {
  nav: { label: "Compare", to: "/compare", group: "Analyze" },
  routes: [{ path: "/compare", element: <Compare /> }],
};
