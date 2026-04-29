import type { ReactNode } from "react";

export interface TopBarProps {
  children: ReactNode;
  className?: string;
  logo?: ReactNode;
  actions?: ReactNode;
}
