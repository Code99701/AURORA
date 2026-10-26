import React from "react";
import styles from "./card.module.css";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
  elevated?: boolean;
  glass?: boolean;
  gradientTop?: boolean;
  radius?: "lg" | "xl" | "2xl";
}

export function Card({
  children,
  interactive = false,
  elevated = false,
  glass = false,
  gradientTop = false,
  radius = "lg",
  className = "",
  ...props
}: CardProps) {
  const radiusClass =
    radius === "2xl" ? styles.radius2Xl : radius === "xl" ? styles.radiusXl : styles.radiusLg;

  const classes = [
    styles.card,
    radiusClass,
    interactive && styles.interactive,
    elevated && styles.elevated,
    glass && styles.glass,
    gradientTop && styles.gradientTop,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} {...props}>
      {children}
    </div>
  );
}
