import React from "react";
import styles from "./skeleton.module.css";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  radius?: "sm" | "md" | "lg" | "full";
}

export function Skeleton({
  width,
  height,
  radius = "md",
  className = "",
  style,
  ...props
}: SkeletonProps) {
  const borderRadius =
    radius === "full"
      ? "9999px"
      : radius === "lg"
      ? "var(--radius-lg, 12px)"
      : radius === "sm"
      ? "var(--radius-sm, 6px)"
      : "var(--radius-md, 8px)";

  return (
    <div
      className={`${styles.skeleton} ${className}`}
      style={{
        width,
        height,
        borderRadius,
        ...style,
      }}
      aria-hidden="true"
      {...props}
    />
  );
}

export function PageSkeleton() {
  return (
    <div className="page-skeleton" aria-label="Loading content" aria-busy="true">
      <Skeleton width="38%" height={18} />
      <Skeleton width="70%" height={42} style={{ marginTop: "0.5rem" }} />
      <Skeleton width="100%" height={160} style={{ marginTop: "1.5rem" }} />
      <Skeleton width="100%" height={240} style={{ marginTop: "1rem" }} />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className={styles.tableSkeleton} aria-label="Loading table data" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={styles.tableRow}>
          <Skeleton width="30%" height={16} />
          <Skeleton width="20%" height={16} />
          <Skeleton width="25%" height={16} />
          <Skeleton width="15%" height={16} />
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className={styles.cardSkeleton} aria-label="Loading card" aria-busy="true">
      <Skeleton width="40%" height={20} />
      <Skeleton width="80%" height={14} />
      <Skeleton width="60%" height={14} />
    </div>
  );
}
