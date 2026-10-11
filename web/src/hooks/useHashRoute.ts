import { useCallback, useEffect, useState } from "react";

export const ROUTES = ["dashboard", "transactions", "budgets", "insights"] as const;
export type Route = (typeof ROUTES)[number];

const read = (): Route => {
  const r = window.location.hash.replace(/^#\/?/, "");
  return (ROUTES as readonly string[]).includes(r) ? (r as Route) : "dashboard";
};

/** Tiny hash router: deep-linkable tabs (#/budgets) with working back/forward, no dependency. */
export function useHashRoute(): [Route, (r: Route) => void] {
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((r: Route) => { window.location.hash = `/${r}`; }, []);
  return [route, go];
}
