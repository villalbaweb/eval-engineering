import type { Feature } from "@/app/routes";
import { Playground } from "./Playground";

export const playgroundFeature: Feature = {
  nav: { label: "Playground", to: "/playground", group: "Build" },
  routes: [{ path: "/playground", element: <Playground /> }],
};
