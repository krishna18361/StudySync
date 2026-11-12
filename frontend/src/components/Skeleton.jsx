/**
 * Shimmering skeleton placeholders shown while data is loading.
 * Purely decorative — hidden from assistive tech.
 */

function Line({ w = "100%", h = 12, className = "" }) {
  return <span className={`sk-line ${className}`} style={{ width: w, height: h }} />;
}

export function SkeletonLine({ w, h, className }) {
  return <Line w={w} h={h} className={className} />;
}

export function DocListSkeleton({ rows = 3 }) {
  return (
    <div className="sk-doc-list" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="sk-doc">
          <Line w="62%" h={12} />
          <Line w="34%" h={9} />
        </div>
      ))}
    </div>
  );
}

export function SummarySkeleton() {
  return (
    <div className="sk-stack" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="sk-card">
          <div className="sk-row">
            <span className="sk-icon" />
            <div className="sk-col">
              <Line w={i === 0 ? "46%" : "34%"} h={14} />
              <Line w="26%" h={10} />
            </div>
          </div>
          {i === 0 ? (
            <div className="sk-col sk-gap">
              <Line w="100%" />
              <Line w="92%" />
              <Line w="70%" />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function QuizSkeleton({ count = 3 }) {
  return (
    <div className="sk-stack" aria-hidden="true">
      <div className="sk-card">
        <Line w="60%" h={14} />
        <div className="sk-col sk-gap">
          <Line w="100%" />
          <Line w="78%" />
        </div>
      </div>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="sk-card">
          <Line w="30%" h={11} />
          <Line w="88%" h={15} />
          <div className="sk-col sk-gap">
            <Line w="100%" h={38} className="sk-pill" />
            <Line w="100%" h={38} className="sk-pill" />
            <Line w="100%" h={38} className="sk-pill" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function PerformanceSkeleton() {
  return (
    <div className="sk-stack" aria-hidden="true">
      <div className="sk-stats">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="sk-card sk-stat">
            <Line w="52%" h={26} />
            <Line w="72%" h={10} />
          </div>
        ))}
      </div>
      <div className="sk-card sk-chart">
        <Line w="34%" h={14} />
        <span className="sk-plot" />
      </div>
      <div className="sk-card">
        <Line w="40%" h={14} />
        <div className="sk-col sk-gap">
          <Line w="100%" h={10} />
          <Line w="82%" h={10} />
          <Line w="64%" h={10} />
        </div>
      </div>
    </div>
  );
}
