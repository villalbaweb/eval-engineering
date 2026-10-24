import type { Feature } from "@/app/routes";
import { Experiments } from "./Experiments";

export const experimentsFeature: Feature = {
  nav: { label: "Experiments", to: "/experiments", group: "Run" },
  routes: [{ path: "/experiments", element: <Experiments /> }],
};
