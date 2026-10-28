import React, { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import styles from "./icon-button.module.css";

export interface IconButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  label: string;
  variant?: "ghost" | "secondary" | "primary" | "danger";
  size?: "sm" | "md";
  busy?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    {
      icon,
      label,
      variant = "ghost",
      size = "md",
      busy = false,
      disabled = false,
      className = "",
      ...props
    },
    ref
  ) {
    const variantClass = styles[variant] || styles.ghost;
    const sizeClass = styles[size] || styles.md;

    return (
      <button
        ref={ref}
        type="button"
        aria-label={label}
        title={label}
        disabled={disabled || busy}
        className={`${styles.iconButton} ${variantClass} ${sizeClass} ${className}`}
        {...props}
      >
        {busy ? (
          <Loader2 size={size === "sm" ? 14 : 16} className={styles.spinner} aria-hidden="true" />
        ) : (
          icon
        )}
      </button>
    );
  }
);
