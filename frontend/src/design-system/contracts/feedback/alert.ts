import type { ReactNode } from "react";

export interface AlertProps {
  children: ReactNode;
  className?: string;
  severity: "success" | "warning" | "error" | "info";
  title?: string;
  dismissible?: boolean;
  onDismiss?: () => void;
}
