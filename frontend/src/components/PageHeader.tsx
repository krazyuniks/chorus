import type { ReactNode } from "react";

/**
 * Dense page header — a single-line heading plus optional sub-text.
 * No hero. No marketing. Designed to read like a section label, not a banner.
 */
export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <header className="flex items-baseline justify-between border-b border-border-muted px-4 py-2">
      <div className="flex items-baseline gap-3">
        <h1 className="text-sm font-semibold text-text">{title}</h1>
        {subtitle && (
          <span className="text-xs text-text-muted">{subtitle}</span>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
