export function PageSkeleton() {
  return (
    <div className="page-skeleton" aria-label="Loading AURORA workspace" aria-busy="true">
      <div className="skeleton" style={{ width: "38%", height: 18 }} />
      <div className="skeleton" style={{ width: "70%", height: 42 }} />
      <div className="skeleton" style={{ width: "100%", height: 160 }} />
      <div className="skeleton" style={{ width: "100%", height: 240 }} />
    </div>
  );
}
