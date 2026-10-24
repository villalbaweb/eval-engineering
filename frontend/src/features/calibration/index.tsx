import type { Feature } from "@/app/routes";
import { Calibration } from "./Calibration";

export const calibrationFeature: Feature = {
  nav: { label: "Calibration", to: "/calibration", group: "Analyze" },
  routes: [{ path: "/calibration", element: <Calibration /> }],
};
