import { useId } from "react";
import type { InputProps } from "../../../contracts/forms";

export function Input({
  className = "",
  label,
  name,
  type = "text",
  placeholder,
  value,
  defaultValue,
  disabled = false,
  required = false,
  error,
  hint,
  onChange,
  ...rest
}: InputProps) {
  const generatedId = useId();
  const inputId = `input-${generatedId}`;
  const hintId = hint ? `hint-${generatedId}` : undefined;
  const errorId = error ? `error-${generatedId}` : undefined;

  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      <label
        htmlFor={inputId}
        className="text-xs font-medium text-text"
      >
        {label}
        {required && <span className="ml-0.5 text-error">*</span>}
      </label>
      <input
        id={inputId}
        name={name}
        type={type}
        placeholder={placeholder}
        value={value}
        defaultValue={defaultValue}
        disabled={disabled}
        required={required}
        onChange={onChange}
        aria-describedby={
          [errorId, hintId].filter(Boolean).join(" ") || undefined
        }
        aria-invalid={error ? true : undefined}
        className={`rounded-sm border px-2 py-1 text-xs text-text bg-surface placeholder:text-text-subtle transition-colors duration-fast ease-default focus:outline-2 focus:outline-offset-0 focus:outline-focus-ring disabled:opacity-50 disabled:cursor-not-allowed ${
          error ? "border-error" : "border-border"
        }`}
        {...rest}
      />
      {hint && !error && (
        <p id={hintId} className="text-[10px] text-text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-[10px] text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
