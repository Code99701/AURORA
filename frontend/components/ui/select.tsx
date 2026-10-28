import React, { forwardRef } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./select.module.css";

export interface SelectOption {
  label: string;
  value: string;
}

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  helperText?: string;
  error?: string;
  options?: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    label,
    helperText,
    error,
    options,
    children,
    id,
    className = "",
    ...props
  },
  ref
) {
  const selectId =
    id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className={styles.selectWrapper}>
      {label && (
        <label htmlFor={selectId} className={styles.label}>
          {label}
        </label>
      )}
      <div className={styles.selectContainer}>
        <select
          ref={ref}
          id={selectId}
          className={`${styles.select} ${error ? styles.hasError : ""} ${className}`}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        <span className={styles.chevron} aria-hidden="true">
          <ChevronDown size={16} />
        </span>
      </div>
      {error ? (
        <span className={styles.errorText} role="alert">
          {error}
        </span>
      ) : helperText ? (
        <span className={styles.helperText}>{helperText}</span>
      ) : null}
    </div>
  );
});
