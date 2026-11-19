"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Notice from "@/components/Notice";
import { uploadSet } from "@/lib/api";
import { rememberVideo } from "@/lib/videoStore";

const ACCEPT = ".mp4,.mov,.m4v,.avi,.webm,video/*";

export default function RecordPage() {
  return (
    <Suspense fallback={<p className="muted">Loading…</p>}>
      <RecordForm />
    </Suspense>
  );
}

function RecordForm() {
  const router = useRouter();
  const params = useSearchParams();

  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [load, setLoad] = useState(params.get("load") ?? "0");
  const [unit, setUnit] = useState(params.get("unit") === "kg" ? "kg" : "lb");
  const [targetReps, setTargetReps] = useState(params.get("reps") ?? "");
  const [rpe, setRpe] = useState("");
  const [progress, setProgress] = useState(null); // null | 0..1 uploading | "analyzing"
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const busy = progress !== null;
  const prefilled = params.has("reps");

  function pick(files) {
    const f = files?.[0];
    if (!f) return;
    setError(null);
    setFile(f);
  }

  async function submit(e) {
    e.preventDefault();
    if (!file) return setError("Choose a video of your set first.");
    setError(null);
    setProgress(0);
    try {
      const result = await uploadSet(
        { file, load: Number(load) || 0, unit, targetReps: Number(targetReps) || null, rpe: Number(rpe) || null },
        (f) => setProgress(f >= 1 ? "analyzing" : f),
      );
      rememberVideo(result.session_id, file);
      router.push(`/sessions/${result.session_id}`);
    } catch (err) {
      setError(err.message);
      setProgress(null);
    }
  }

  return (
    <div className="split">
      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="section">
          <h1>Record a set</h1>
          <p>
            {prefilled
              ? "Your next set is filled in below. Do the set, film it from the side, then upload the clip."
              : "Upload a video of one set of squats. Enter what you lifted so LiftLens can set your next session."}
          </p>
        </div>

        <label
          className={`dropzone${dragging ? " active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files);
          }}
        >
          <input type="file" accept={ACCEPT} onChange={(e) => pick(e.target.files)} disabled={busy} />
          {file ? (
            <>
              <strong>{file.name}</strong>
              <span className="muted small">
                {(file.size / (1024 * 1024)).toFixed(1)} MB. Click to choose a different video.
              </span>
            </>
          ) : (
            <>
              <strong>Choose a video or drop it here</strong>
              <span className="muted small">MP4 or MOV from your phone works.</span>
            </>
          )}
        </label>

        {preview && <video className="video" src={preview} controls muted playsInline />}

        <div className="row-2">
          <label className="field">
            <span>
              Weight <span className="hint">0 for bodyweight</span>
            </span>
            <input type="number" min="0" step="0.5" inputMode="decimal" value={load} onChange={(e) => setLoad(e.target.value)} />
          </label>
          <fieldset className="choices">
            <legend>Unit</legend>
            {["lb", "kg"].map((u) => (
              <label key={u}>
                <input type="radio" name="unit" value={u} checked={unit === u} onChange={() => setUnit(u)} />
                <span>{u}</span>
              </label>
            ))}
          </fieldset>
        </div>

        <div className="row-2">
          <label className="field">
            <span>
              Target reps <span className="hint">what you planned</span>
            </span>
            <input type="number" min="1" max="100" inputMode="numeric" value={targetReps} onChange={(e) => setTargetReps(e.target.value)} />
          </label>
          <label className="field">
            <span>
              How hard was it? <span className="hint">RPE, optional</span>
            </span>
            <select value={rpe} onChange={(e) => setRpe(e.target.value)}>
              <option value="">Skip</option>
              {[...Array(10)].map((_, i) => {
                const v = 10 - i;
                const note = { 10: " (couldn't do another rep)", 8: " (2 reps left)", 6: " (moderate)", 3: " (easy)" }[v] || "";
                return (
                  <option key={v} value={v}>
                    {v}
                    {note}
                  </option>
                );
              })}
            </select>
          </label>
        </div>

        {error && <Notice kind="error">{error}</Notice>}

        {busy && (
          <div className="section" aria-live="polite">
            <div className={`progress${progress === "analyzing" ? " working" : ""}`}>
              <div style={{ width: `${progress === "analyzing" ? 100 : Math.round(progress * 100)}%` }} />
            </div>
            <p className="muted small">
              {progress === "analyzing"
                ? "Checking every rep. This takes a few seconds per second of video."
                : `Uploading ${Math.round(progress * 100)}%`}
            </p>
          </div>
        )}

        <p>
          <button className="button" type="submit" disabled={busy}>
            {busy ? "Analyzing…" : "Analyze set"}
          </button>
        </p>
      </form>

      <aside className="section" aria-labelledby="filming">
        <h2 id="filming">Filming tips</h2>
        <ul className="checklist">
          <li>Stand side-on to the camera. Facing it makes the angles wrong.</li>
          <li>Keep your whole body in frame, feet to head, for the entire set.</li>
          <li>Prop the phone at about hip height, 2 to 3 meters away.</li>
          <li>One set per video. Start recording before your first rep.</li>
          <li>Only you in the shot. Don't film other people at the gym.</li>
        </ul>
        <p className="muted small">
          Your video is analyzed on the LiftLens server and deleted right after. Only the rep measurements are kept.
        </p>
      </aside>
    </div>
  );
}
