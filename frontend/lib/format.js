// Shared wording, so the same thing is named the same way on every page.

export const DECISION_LABEL = {
  increase: "Progress",
  hold: "Hold",
  reduce: "Back off",
  deload: "Deload",
  retest: "Re-record",
};

export const ERROR_LABEL = {
  shallow_depth: "Too shallow",
  forward_lean: "Leaning forward",
};

export function loadText(load, unit) {
  return load > 0 ? `${formatNumber(load)} ${unit}` : "Bodyweight";
}

export function formatNumber(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, "");
}

export function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function percent(score) {
  return score == null ? "–" : `${Math.round(score * 100)}%`;
}

// Link to the record page with the next prescription pre-filled.
export function recordHref(next) {
  if (!next) return "/record";
  const q = new URLSearchParams({
    load: String(next.load),
    unit: next.unit,
    reps: String(next.target_reps),
  });
  return `/record?${q}`;
}
