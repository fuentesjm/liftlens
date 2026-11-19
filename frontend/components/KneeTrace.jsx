"use client";

import { useEffect, useRef, useState } from "react";

// Knee angle over the whole set. The line dips at every rep, like the lifter
// does; each rep's span is tinted green (passed) or red (failed), and the
// dashed line marks the depth a rep has to reach. Click a rep to replay it.
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

  const height = width < 560 ? 220 : 280;
  const m = { top: 30, right: 12, bottom: 26, left: 40 };
  const depth = report.thresholds.max_bottom_knee_angle;
  const tMax = trace.t[trace.t.length - 1] || 1;
  const yMin = Math.min(70, Math.floor((Math.min(...trace.knee) - 5) / 10) * 10);
  const yMax = 185;

  const x = (t) => m.left + (t / tMax) * (width - m.left - m.right);
  const y = (a) => m.top + ((yMax - a) / (yMax - yMin)) * (height - m.top - m.bottom);

  const points = trace.t.map((t, i) => `${x(t).toFixed(1)},${y(trace.knee[i]).toFixed(1)}`).join(" ");
  const yTicks = [90, 120, 150, 180].filter((v) => v >= yMin);
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
              {v}°
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={height - 6} textAnchor="middle">
            {t}s
          </text>
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
          Depth line {depth}°
        </text>

        <polyline className="line" points={points} />

        {report.reps.map((r) => (
          <circle
            key={r.number}
            className={`bottom ${r.passed ? "pass" : "fail"}`}
            cx={x(r.bottom_time)}
            cy={y(r.bottom_knee_angle)}
            r={6}
          />
        ))}

        {currentTime != null && currentTime <= tMax && (
          <line className="playhead" x1={x(currentTime)} x2={x(currentTime)} y1={m.top} y2={height - m.bottom} />
        )}
      </svg>
      <figcaption className="trace-legend">
        <span>Knee angle (180° = standing straight)</span>
        <span>
          <i className="swatch" style={{ background: "var(--pass-wash)", outline: "1px solid var(--plate-green)" }} />
          Rep passed
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--fail-wash)", outline: "1px solid var(--plate-red)" }} />
          Rep failed
        </span>
        <span>Dot = deepest point. Click a rep to replay it.</span>
      </figcaption>
    </figure>
  );
}
