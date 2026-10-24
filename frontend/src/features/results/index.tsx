import type { Feature } from "@/app/routes";
import { ExperimentDetail } from "./ExperimentDetail";

export const resultsFeature: Feature = {
  routes: [{ path: "/experiments/:id", element: <ExperimentDetail /> }],
};
