import type { ReactNode } from "react";

export interface HeroProps {
  children: ReactNode;
  className?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}
