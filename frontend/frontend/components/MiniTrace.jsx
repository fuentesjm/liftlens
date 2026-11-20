"use client";

import { useEffect, useRef, useState } from "react";

// Small, non-interactive knee-angle chart for the home page. The line draws
// itself once on load (skipped when the user prefers reduced motion).
export default function MiniTrace({ trace, reps, depth, height = 170, label }) {
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

  if (!trace || trace.t.length < 2) return null;

  const m = { top: 22, right: 6, bottom: 8, left: 6 };
  const tMax = trace.t[trace.t.length - 1] || 1;
  const yMin = Math.min(70, Math.min(...trace.knee) - 8);
  const yMax = 185;
  const x = (t) => m.left + (t / tMax) * (width - m.left - m.right);
  const y = (a) => m.top + ((yMax - a) / (yMax - yMin)) * (height - m.top - m.bottom);
  const points = trace.t.map((t, i) => `${x(t).toFixed(1)},${y(trace.knee[i]).toFixed(1)}`).join(" ");

  return (
    <div className="trace mini" ref={box}>
      <svg width={width} height={height} role="img" aria-label={label}>
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
          <circle key={r.number} className={`bottom ${r.passed ? "pass" : "fail"}`} cx={x(r.bottom_time)} cy={y(r.bottom_knee_angle)} r={5} />
        ))}
      </svg>
    </div>
  );
}

// A made-up three-rep set (rep 2 too shallow) for the first-visit page.
export function sampleSet() {
  const t = [];
  const knee = [];
  const dips = [
    { start: 0.8, bottom: 88 },
    { start: 3.4, bottom: 117 },
    { start: 6.0, bottom: 86 },
  ];
  for (let i = 0; i <= 88; i++) {
    const time = i / 10;
    let angle = 176;
    for (const d of dips) {
      const p = (time - d.start) / 1.8;
      if (p >= 0 && p <= 1) angle = 176 - (176 - d.bottom) * (1 - Math.cos(2 * Math.PI * p)) / 2;
    }
    t.push(time);
    knee.push(angle);
  }
  const reps = dips.map((d, i) => ({
    number: i + 1,
    start_time: d.start,
    end_time: d.start + 1.8,
    bottom_time: d.start + 0.9,
    bottom_knee_angle: d.bottom,
    passed: d.bottom <= 100,
  }));
  return { trace: { t, knee }, reps };
}
