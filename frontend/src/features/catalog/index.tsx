import type { Feature } from "@/app/routes";
import { Catalog } from "./Catalog";

export const catalogFeature: Feature = {
  nav: { label: "Catalog", to: "/catalog", group: "Build" },
  routes: [{ path: "/catalog", element: <Catalog /> }],
};
