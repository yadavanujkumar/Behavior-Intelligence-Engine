import React, { useState } from "react";

/**
 * VideoFeed – renders the MJPEG stream from the API gateway.
 *
 * The browser consumes the MJPEG stream as a regular <img> src,
 * which handles chunked multipart/x-mixed-replace automatically.
 */
export default function VideoFeed({ apiBase, showHeatmap }) {
  const [imgError, setImgError] = useState(false);
  const feedUrl = showHeatmap
    ? `${apiBase}/video_feed/heatmap`
    : `${apiBase}/video_feed`;

  return (
    <div className="bg-slate-800 rounded-xl overflow-hidden shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-700">
        <h2 className="font-semibold text-slate-200">
          📹 Live Feed {showHeatmap ? "— Heatmap" : ""}
        </h2>
        <span className="text-xs text-slate-400">MJPEG Stream</span>
      </div>

      <div className="relative bg-black" style={{ aspectRatio: "16/9" }}>
        {imgError ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm p-8">
            ⚠ Video feed unavailable. Ensure the API gateway is running and a
            camera/video source is configured.
          </div>
        ) : (
          <img
            key={feedUrl}          // force re-mount when URL changes
            src={feedUrl}
            alt="Live surveillance feed"
            className="w-full h-full object-contain"
            onError={() => setImgError(true)}
          />
        )}
      </div>
    </div>
  );
}
