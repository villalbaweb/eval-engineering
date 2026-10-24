import type { Feature } from "@/app/routes";
import { DataSources } from "./DataSources";

export const dataSourcesFeature: Feature = {
  nav: { label: "Data sources", to: "/data", group: "Build" },
  routes: [{ path: "/data", element: <DataSources /> }],
};
