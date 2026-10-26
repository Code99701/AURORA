import React from "react";
import styles from "./badge.module.css";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | "neutral"
    | "primary"
    | "purple"
    | "coral"
    | "teal"
    | "amber"
    | "pink"
    | "success"
    | "warning"
    | "danger"
    | "info";
  icon?: React.ReactNode;
}

export function Badge({
  children,
  variant = "neutral",
  icon,
  className = "",
  ...props
}: BadgeProps) {
  const variantClass = styles[variant] || styles.neutral;

  return (
    <span className={`${styles.badge} ${variantClass} ${className}`} {...props}>
      {icon}
      <span>{children}</span>
    </span>
  );
}
