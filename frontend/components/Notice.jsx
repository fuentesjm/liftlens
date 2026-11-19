// Error or warning block. Long commands in messages are shown as code.
export default function Notice({ kind = "warning", title, children }) {
  return (
    <div className={`notice${kind === "error" ? " error" : ""}`} role={kind === "error" ? "alert" : "status"}>
      {title && <p><strong>{title}</strong></p>}
      {typeof children === "string" ? <p>{withCode(children)}</p> : children}
    </div>
  );
}

// "... Start it with: uvicorn backend.api.main:app --reload" -> command as <code>.
function withCode(text) {
  const m = text.match(/^(.*?:\s)((?:uvicorn|python) .+)$/);
  if (!m) return text;
  return (
    <>
      {m[1]}
      <code>{m[2]}</code>
    </>
  );
}
