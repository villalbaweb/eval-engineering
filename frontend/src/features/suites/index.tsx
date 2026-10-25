import type { Feature } from "@/app/routes";
import { Suites } from "./Suites";

export const suitesFeature: Feature = {
  nav: { label: "Suites", to: "/suites", group: "Build" },
  routes: [{ path: "/suites", element: <Suites /> }],
};
