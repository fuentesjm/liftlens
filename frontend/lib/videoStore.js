// Keeps the just-uploaded video in the browser (as an object URL) so the results
// page can replay it next to the chart. The server deletes uploaded videos after
// analysis, so the replay is only available in the tab that uploaded it.

const videos = new Map();

export function rememberVideo(sessionId, file) {
  videos.set(sessionId, URL.createObjectURL(file));
}

export function videoFor(sessionId) {
  return videos.get(sessionId) || null;
}
