"use client";

import { useEffect, useRef, useState } from "react";

// Small, non-interactive depth chart for the home page. The line draws
// itself once on load (skipped when the user prefers reduced motion).
// `values` is the series to plot (thigh angle above parallel for new sessions,
// knee angle for older ones); `bottom(r)` gives a rep's value at its deepest point.
export default function MiniTrace({ trace, values, reps, depth, bottom, ignored = [], yMax = 95, height = 170, label }) {
  const box = useRef(null);
  const line = useRef(null);
  const [width, setWidth] = useState(480);

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(240, e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const el = line.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const length = el.getTotalLength();
    el.style.strokeDasharray = `${length}`;
    el.style.strokeDashoffset = `${length}`;
    el.getBoundingClientRect(); // apply the start state before animating
    el.style.transition = "stroke-dashoffset 1.4s ease-out";
    el.style.strokeDashoffset = "0";
  }, [trace]);

  if (!trace || trace.t.length < 2 || !values) return null;

  const m = { top: 22, right: 6, bottom: 8, left: 6 };
  const tMax = trace.t[trace.t.length - 1] || 1;
  const finite = values.filter((v) => v != null && Number.isFinite(v));
  const yMin = Math.min(depth - 20, Math.min(...finite) - 8);
  const x = (t) => m.left + (t / tMax) * (width - m.left - m.right);
  const y = (a) => m.top + ((yMax - a) / (yMax - yMin)) * (height - m.top - m.bottom);
  const points = trace.t
    .map((t, i) => (Number.isFinite(values[i]) ? `${x(t).toFixed(1)},${y(values[i]).toFixed(1)}` : null))
    .filter(Boolean)
    .join(" ");

  return (
    <div className="trace mini" ref={box}>
      <svg width={width} height={height} role="img" aria-label={label}>
        {ignored.map((g, i) => (
          <rect
            key={`ignored-${i}`}
            className="band ignored"
            x={x(g.start_time)}
            y={m.top}
            width={Math.max(2, x(g.end_time) - x(g.start_time))}
            height={height - m.top - m.bottom}
          />
        ))}
        {reps.map((r) => (
          <g key={r.number}>
            <rect
              className={`band ${r.passed ? "pass" : "fail"}`}
              x={x(r.start_time)}
              y={m.top}
              width={Math.max(2, x(r.end_time) - x(r.start_time))}
              height={height - m.top - m.bottom}
              style={{ cursor: "default" }}
            />
            <text className="rep-label" x={(x(r.start_time) + x(r.end_time)) / 2} y={m.top - 7} textAnchor="middle">
              {r.number}
            </text>
          </g>
        ))}
        <line className="depth" x1={m.left} x2={width - m.right} y1={y(depth)} y2={y(depth)} />
        <polyline ref={line} className="line" points={points} />
        {reps.map((r) => (
          <circle key={r.number} className={`bottom ${r.passed ? "pass" : "fail"}`} cx={x(r.bottom_time)} cy={y(bottom(r))} r={5} />
        ))}
      </svg>
    </div>
  );
}

// A made-up three-rep set (rep 2 too shallow) for the first-visit page.
// Values are the thigh angle above parallel (88 = standing, 0 = parallel).
export function sampleSet() {
  const t = [];
  const thigh = [];
  const dips = [
    { start: 0.8, bottom: 6 },
    { start: 3.4, bottom: 27 },
    { start: 6.0, bottom: 4 },
  ];
  for (let i = 0; i <= 88; i++) {
    const time = i / 10;
    let angle = 88;
    for (const d of dips) {
      const p = (time - d.start) / 1.8;
      if (p >= 0 && p <= 1) angle = 88 - (88 - d.bottom) * (1 - Math.cos(2 * Math.PI * p)) / 2;
    }
    t.push(time);
    thigh.push(angle);
  }
  const reps = dips.map((d, i) => ({
    number: i + 1,
    start_time: d.start,
    end_time: d.start + 1.8,
    bottom_time: d.start + 0.9,
    bottom_thigh_angle: d.bottom,
    passed: d.bottom <= 15,
  }));
  return { trace: { t, thigh }, reps };
}
