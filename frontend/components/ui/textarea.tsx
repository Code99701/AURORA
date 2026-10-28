import React, { forwardRef } from "react";
import styles from "./textarea.module.css";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    { label, helperText, error, id, className = "", ...props },
    ref
  ) {
    const textareaId =
      id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className={styles.textareaWrapper}>
        {label && (
          <label htmlFor={textareaId} className={styles.label}>
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={`${styles.textarea} ${error ? styles.hasError : ""} ${className}`}
          {...props}
        />
        {error ? (
          <span className={styles.errorText} role="alert">
            {error}
          </span>
        ) : helperText ? (
          <span className={styles.helperText}>{helperText}</span>
        ) : null}
      </div>
    );
  }
);
