"use client";

import React, { useState, useId } from "react";
import styles from "./tooltip.module.css";

export interface TooltipProps {
  content: string;
  children: React.ReactElement<React.HTMLAttributes<HTMLElement>>;
  className?: string;
}

export function Tooltip({ content, children, className = "" }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = useId();

  return (
    <div
      className={`${styles.tooltipWrapper} ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {React.cloneElement(children, {
        "aria-describedby": visible ? tooltipId : undefined,
      })}
      {visible && (
        <div id={tooltipId} role="tooltip" className={styles.tooltip}>
          {content}
        </div>
      )}
    </div>
  );
}
