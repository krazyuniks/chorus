import {
  Outlet,
  createRootRouteWithContext,
  Link,
} from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";
import { TopBar } from "@/design-system/designs/dense/navigation/TopBar";
import { cn } from "@/lib/utils";

interface RouterContext {
  queryClient: QueryClient;
}

const NAV: { to: string; label: string }[] = [
  { to: "/", label: "Workflows" },
  { to: "/decision-trail", label: "Decision Trail" },
  { to: "/tool-verdicts", label: "Tool Verdicts" },
  { to: "/registry", label: "Registry" },
  { to: "/grants", label: "Grants" },
  { to: "/routing", label: "Routing" },
  { to: "/eval", label: "Eval" },
];

function NavLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      activeOptions={{ exact: to === "/" }}
      className="text-text-muted hover:text-text transition-colors"
      activeProps={{ className: "text-text font-medium" }}
    >
      {label}
    </Link>
  );
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
});

function RootComponent() {
  return (
    <div className={cn("flex h-full flex-col bg-surface text-text")}>
      <TopBar
        logo={
          <span className="mono text-xs">
            chorus<span className="text-text-muted">/lighthouse</span>
          </span>
        }
        actions={
          <span className="text-[10px] uppercase tracking-wide text-text-subtle">
            phase 1 · sandbox
          </span>
        }
      >
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} label={item.label} />
        ))}
      </TopBar>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
