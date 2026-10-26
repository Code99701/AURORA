import React, { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import styles from "./button.module.css";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
  busy?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    children,
    className = "",
    variant = "primary",
    size = "md",
    busy = false,
    disabled = false,
    leftIcon,
    rightIcon,
    ...props
  },
  ref
) {
  const variantClass = styles[variant] || styles.primary;
  const sizeClass = styles[size] || styles.md;

  return (
    <button
      ref={ref}
      className={`${styles.button} ${variantClass} ${sizeClass} ${className}`}
      disabled={disabled || busy}
      {...props}
    >
      {busy ? (
        <Loader2 size={16} className={styles.spinner} aria-hidden="true" />
      ) : (
        leftIcon
      )}
      <span>{children}</span>
      {!busy && rightIcon}
    </button>
  );
});
