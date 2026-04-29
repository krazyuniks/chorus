import type { HeroProps } from "../../contracts/content";

export function Hero({
  children,
  className = "",
  title,
  subtitle,
  actions,
}: HeroProps) {
  return (
    <section
      className={`flex flex-col px-4 py-8 ${className}`}
    >
      <h1 className="text-xl font-bold text-text">{title}</h1>
      {subtitle && (
        <p className="mt-1 max-w-xl text-sm text-text-muted">{subtitle}</p>
      )}
      {children && <div className="mt-3">{children}</div>}
      {actions && <div className="mt-4 flex gap-2">{actions}</div>}
    </section>
  );
}
