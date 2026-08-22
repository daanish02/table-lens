export function Skeleton({ width, height = 14 }: { width?: string | number; height?: string | number }) {
  return (
    <div style={{ width, height, background: "var(--surface)", borderRadius: 2, overflow: "hidden", position: "relative" }}>
      <div className="skeleton-shimmer" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 2, padding: "14px 16px" }}>
      <Skeleton width="55%" height={13} />
      <div style={{ marginTop: 8 }}>
        <Skeleton width="70%" height={11} />
      </div>
      <div style={{ marginTop: 12 }}>
        <Skeleton width="100%" height={11} />
      </div>
      <div style={{ marginTop: 6 }}>
        <Skeleton width="85%" height={11} />
      </div>
    </div>
  );
}
