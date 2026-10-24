import type { Feature } from "@/app/routes";
import { Datasets } from "./Datasets";

export const datasetsFeature: Feature = {
  nav: { label: "Datasets", to: "/datasets", group: "Build" },
  routes: [{ path: "/datasets", element: <Datasets /> }],
};
