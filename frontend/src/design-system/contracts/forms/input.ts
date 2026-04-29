import type { ReactNode, ChangeEventHandler } from "react";

export interface InputProps {
  className?: string;
  label: string;
  name: string;
  type?: "text" | "email" | "password" | "number" | "search" | "tel" | "url";
  placeholder?: string;
  value?: string;
  defaultValue?: string;
  disabled?: boolean;
  required?: boolean;
  error?: ReactNode;
  hint?: ReactNode;
  onChange?: ChangeEventHandler<HTMLInputElement>;
  "aria-describedby"?: string;
}
