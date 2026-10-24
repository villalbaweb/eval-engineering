import type { Feature } from "@/app/routes";
import { TrialPage } from "./TrialPage";

export const transcriptsFeature: Feature = {
  routes: [{ path: "/trials/:id", element: <TrialPage /> }],
};
