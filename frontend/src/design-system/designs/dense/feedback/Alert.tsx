import { useState } from "react";
import type { AlertProps } from "../../contracts/feedback";

const severityStyles = {
  success: "border-success bg-success/10 text-success",
  warning: "border-warning bg-warning/10 text-warning",
  error: "border-error bg-error/10 text-error",
  info: "border-info bg-info/10 text-info",
} as const;

export function Alert({
  children,
  className = "",
  severity,
  title,
  dismissible = false,
  onDismiss,
}: AlertProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <div
      role="alert"
      className={`flex items-center gap-2 rounded-sm border-l-2 px-2 py-1.5 text-xs ${severityStyles[severity]} ${className}`}
    >
      <div className="flex-1">
        {title && <span className="font-semibold">{title}: </span>}
        <span className={title ? "opacity-90" : ""}>{children}</span>
      </div>
      {dismissible && (
        <button
          onClick={handleDismiss}
          className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
          aria-label="Dismiss alert"
        >
          <svg
            className="h-3 w-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
