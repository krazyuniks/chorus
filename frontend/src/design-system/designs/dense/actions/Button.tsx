import type { ButtonProps } from "../../contracts/actions";

export function Button({
  children,
  className = "",
  type = "button",
  disabled = false,
  onClick,
  href,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center px-3 py-1 text-xs font-medium rounded-sm bg-primary text-text-on-primary transition-colors duration-fast ease-default hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus-ring disabled:opacity-50 disabled:pointer-events-none";

  if (href && !disabled) {
    return (
      <a href={href} className={`${base} ${className}`} {...rest}>
        {children}
      </a>
    );
  }

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
