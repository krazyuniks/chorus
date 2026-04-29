import type { TopBarProps } from "../../contracts/navigation";

export function TopBar({
  children,
  className = "",
  logo,
  actions,
}: TopBarProps) {
  return (
    <nav
      className={`flex items-center justify-between border-b border-border bg-surface-raised px-4 py-1.5 ${className}`}
    >
      {logo && (
        <div className="flex-shrink-0 text-xs font-bold text-text">{logo}</div>
      )}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        {children}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </nav>
  );
}
