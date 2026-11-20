"use client";

import { useEffect, useRef, useState } from "react";

// Depth over the whole set: how far the thigh is above parallel (90 = standing,
// 0 = parallel). The line dips at every rep, like the lifter does; each rep's
// span is tinted green (passed) or red (failed), the dashed line marks the
// depth a rep has to reach, and grey spans are setup movements that weren't
// counted. Older sessions without the thigh trace fall back to the knee angle.
// Click a rep to replay it.
export default function KneeTrace({ report, currentTime = null, onSeek }) {
  const box = useRef(null);
  const [width, setWidth] = useState(800);

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  const trace = report.trace;
  if (!trace || trace.t.length < 2) {
    return (
      <p className="muted">The angle chart isn't available for this session (it was saved before charts were added).</p>
    );
  }

  const thigh = Array.isArray(trace.thigh) && report.thresholds.max_thigh_above_parallel != null;
  const values = thigh ? trace.thigh : trace.knee;
  const depth = thigh ? report.thresholds.max_thigh_above_parallel : report.thresholds.max_bottom_knee_angle;
  const bottomOf = (r) => (thigh ? r.bottom_thigh_angle : r.bottom_knee_angle);
  const finite = values.filter((v) => v != null && Number.isFinite(v));

  const height = width < 560 ? 220 : 280;
  const m = { top: 30, right: 12, bottom: 26, left: 52 };
  const tMax = trace.t[trace.t.length - 1] || 1;
  const yMin = thigh
    ? Math.min(-10, Math.floor((Math.min(...finite) - 5) / 10) * 10)
    : Math.min(70, Math.floor((Math.min(...finite) - 5) / 10) * 10);
  const yMax = thigh ? 95 : 185;

  const x = (t) => m.left + (t / tMax) * (width - m.left - m.right);
  const y = (a) => m.top + ((yMax - a) / (yMax - yMin)) * (height - m.top - m.bottom);

  const points = trace.t
    .map((t, i) => (Number.isFinite(values[i]) ? `${x(t).toFixed(1)},${y(values[i]).toFixed(1)}` : null))
    .filter(Boolean)
    .join(" ");
  const yTicks = (thigh ? [0, 30, 60, 90] : [90, 120, 150, 180]).filter((v) => v >= yMin);
  const tickLabel = (v) => (thigh && v === 0 ? "parallel" : `${v}°`);
  const xStep = tMax > 20 ? 5 : tMax > 8 ? 2 : 1;
  const xTicks = Array.from({ length: Math.floor(tMax / xStep) + 1 }, (_, i) => i * xStep);

  return (
    <figure className="trace" ref={box} style={{ margin: 0 }}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Knee angle over time. ${report.rep_count} reps; ${report.reps_passed} passed.`}
      >
        {yTicks.map((v) => (
          <g key={v}>
            <line className="grid" x1={m.left} x2={width - m.right} y1={y(v)} y2={y(v)} />
            <text x={m.left - 8} y={y(v) + 4} textAnchor="end">
              {tickLabel(v)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={height - 6} textAnchor="middle">
            {t}s
          </text>
        ))}

        {(report.ignored_movements || []).map((g, i) => (
          <g key={`ignored-${i}`}>
            <rect
              className="band ignored"
              x={x(g.start_time)}
              y={m.top}
              width={Math.max(2, x(g.end_time) - x(g.start_time))}
              height={height - m.top - m.bottom}
            >
              <title>Not counted: {g.reason}</title>
            </rect>
            <text className="ignored-label" x={(x(g.start_time) + x(g.end_time)) / 2} y={m.top - 10} textAnchor="middle">
              setup
            </text>
          </g>
        ))}

        {report.reps.map((r) => (
          <g key={r.number}>
            <rect
              className={`band ${r.passed ? "pass" : "fail"}`}
              x={x(r.start_time)}
              y={m.top}
              width={Math.max(2, x(r.end_time) - x(r.start_time))}
              height={height - m.top - m.bottom}
              onClick={() => onSeek?.(r.start_time)}
            >
              <title>{`Rep ${r.number}: ${r.passed ? "passed" : "failed"}. Click to replay.`}</title>
            </rect>
            <text className="rep-label" x={(x(r.start_time) + x(r.end_time)) / 2} y={m.top - 10} textAnchor="middle">
              {r.number}
            </text>
          </g>
        ))}

        <line className="depth" x1={m.left} x2={width - m.right} y1={y(depth)} y2={y(depth)} />
        <text className="depth-label" x={m.left + 6} y={y(depth) - 6}>
          {thigh ? `Depth line: ${depth}° above parallel` : `Depth line ${depth}°`}
        </text>

        <polyline className="line" points={points} />

        {report.reps.map((r) => (
          <circle
            key={r.number}
            className={`bottom ${r.passed ? "pass" : "fail"}`}
            cx={x(r.bottom_time)}
            cy={y(bottomOf(r))}
            r={6}
          />
        ))}

        {currentTime != null && currentTime <= tMax && (
          <line className="playhead" x1={x(currentTime)} x2={x(currentTime)} y1={m.top} y2={height - m.bottom} />
        )}
      </svg>
      <figcaption className="trace-legend">
        <span>{thigh ? "Thigh angle above parallel (90° = standing)" : "Knee angle (180° = standing straight)"}</span>
        <span>
          <i className="swatch" style={{ background: "var(--pass-wash)", outline: "1px solid var(--plate-green)" }} />
          Rep passed
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--fail-wash)", outline: "1px solid var(--plate-red)" }} />
          Rep failed
        </span>
        {(report.ignored_movements || []).length > 0 && (
          <span>
            <i className="swatch" style={{ background: "var(--ignored-wash)", outline: "1px solid var(--steel)" }} />
            Setup, not counted
          </span>
        )}
        <span>Dot = deepest point. Click a rep to replay it.</span>
      </figcaption>
    </figure>
  );
}
