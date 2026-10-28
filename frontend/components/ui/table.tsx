import React from "react";
import styles from "./table.module.css";

export function Table({
  children,
  className = "",
  containerClassName = "",
  ...props
}: React.TableHTMLAttributes<HTMLTableElement> & { containerClassName?: string }) {
  return (
    <div className={`${styles.tableContainer} ${containerClassName}`}>
      <table className={`${styles.table} ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

export function TableHeader({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={`${styles.thead} ${className}`} {...props}>
      {children}
    </thead>
  );
}

export function TableBody({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={`${styles.tbody} ${className}`} {...props}>
      {children}
    </tbody>
  );
}

export function TableRow({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={className} {...props}>
      {children}
    </tr>
  );
}

export function TableHead({
  children,
  className = "",
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={`${styles.th} ${className}`} {...props}>
      {children}
    </th>
  );
}

export function TableCell({
  children,
  className = "",
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`${styles.td} ${className}`} {...props}>
      {children}
    </td>
  );
}
