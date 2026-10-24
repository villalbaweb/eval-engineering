import type { Feature } from "@/app/routes";
import { Annotate } from "./Annotate";

export const annotateFeature: Feature = {
  nav: { label: "Annotate", to: "/annotate", group: "Analyze" },
  routes: [{ path: "/annotate", element: <Annotate /> }],
};
