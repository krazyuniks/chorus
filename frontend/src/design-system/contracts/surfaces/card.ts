import type { ReactNode, MouseEventHandler } from "react";

export interface CardProps {
  children: ReactNode;
  className?: string;
  header?: ReactNode;
  footer?: ReactNode;
  interactive?: boolean;
  href?: string;
  onClick?: MouseEventHandler<HTMLElement>;
}
