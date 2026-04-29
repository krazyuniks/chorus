import type { CardProps } from "../../../contracts/surfaces";

export function Card({
  children,
  className = "",
  header,
  footer,
  interactive = false,
  href,
  onClick,
}: CardProps) {
  const base =
    "rounded-sm border border-border bg-surface p-3 text-xs transition-colors duration-fast ease-default";
  const interactiveStyles = interactive
    ? "hover:bg-surface-raised cursor-pointer"
    : "";

  const content = (
    <>
      {header && (
        <div className="mb-2 text-sm font-semibold text-text">{header}</div>
      )}
      <div className="text-text-muted leading-snug">{children}</div>
      {footer && (
        <div className="mt-2 border-t border-border-muted pt-2 text-text-subtle">
          {footer}
        </div>
      )}
    </>
  );

  if (href) {
    return (
      <a
        href={href}
        className={`block ${base} ${interactiveStyles} ${className}`}
      >
        {content}
      </a>
    );
  }

  return (
    <div
      className={`${base} ${interactiveStyles} ${className}`}
      onClick={onClick}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {content}
    </div>
  );
}
