// Calls to the LiftLens FastAPI server. The address comes from NEXT_PUBLIC_API_URL
// (see .env.local.example); no secrets live in the frontend.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const UNREACHABLE =
  `Can't reach the LiftLens server at ${API_URL}. Start it from the project folder with: ` +
  "uvicorn backend.api.main:app --reload";

function detailText(body, fallback) {
  const d = body && body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    // FastAPI validation errors: [{loc: ["body", "rpe"], msg: "..."}]
    return d.map((e) => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join("; ");
  }
  return fallback;
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(API_URL + path, { cache: "no-store", ...options });
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }
  if (!res.ok) {
    let body = null;
    try {
      body = await res.json();
    } catch {}
    throw new ApiError(detailText(body, `Request failed (${res.status})`), res.status);
  }
  return res.json();
}

async function orNull(promise) {
  try {
    return await promise;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export const getHealth = () => request("/health");
export const getSessions = () => request("/sessions");
export const getSession = (id) => request(`/sessions/${encodeURIComponent(id)}`);
export const getNextWorkout = (exercise = "squat") =>
  orNull(request(`/next-workout?exercise=${exercise}`));
export const getPlan = () => orNull(request("/plan"));
export const createPlan = (profile) =>
  request("/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

// Upload with progress (fetch can't report upload progress, XMLHttpRequest can).
// onProgress(fraction) is called while the file uploads; after that the server
// analyzes the video, which can take a while for long clips.
export function uploadSet({ file, load, unit, targetReps, rpe }, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("exercise", "squat");
  form.append("load", String(load || 0));
  form.append("unit", unit);
  if (targetReps) form.append("target_reps", String(targetReps));
  if (rpe) form.append("rpe", String(rpe));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/analyze`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.upload.onload = () => onProgress?.(1);
    xhr.onerror = () => reject(new ApiError(UNREACHABLE, 0));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response);
      else reject(new ApiError(detailText(xhr.response, `Upload failed (${xhr.status})`), xhr.status));
    };
    xhr.send(form);
  });
}
