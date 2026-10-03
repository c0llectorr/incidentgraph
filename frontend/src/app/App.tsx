import { RouterProvider } from "react-router-dom";
import { router } from "./router";

/** Composition root of the frontend. Providers stay minimal by design
 * (PRD §12.8: small state strategy — React state only for this MVP). */
export default function App() {
  return <RouterProvider router={router} />;
}
