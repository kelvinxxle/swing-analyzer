"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CloudUploadIcon, VideoIcon } from "@/components/icons";
import { ProgressBar } from "@/components/ProgressBar";
import {
  analyzeEndpoint,
  destinationFor,
  parseAnalyzeResponse,
  storeAnalysis,
} from "@/lib/analysis";

// Max raw FILE size, in bytes. This is measured against `file.size` (the file
// bytes only, before multipart framing) and matches the backend's DEFAULT
// `MAX_UPLOAD_BYTES` cap (50MB), which is likewise a FILE-bytes cap. Operators
// can configure the backend cap independently via the `MAX_UPLOAD_BYTES` env
// var; this constant is the UI's copy of the shipped default. The backend
// tolerates a small multipart-overhead envelope on top of its cap in the
// pre-parse Content-Length guard, so a file at exactly this limit is never
// wrongly rejected with a 413.
const MAX_BYTES = 50 * 1024 * 1024;

type Phase = "idle" | "uploading" | "analyzing" | "error";

/**
 * Upload surface wired to the live `/analyze` loop (M3). Selecting a video posts
 * it to the same-origin proxy with real upload-progress, then routes to the
 * results or error screen based on the API response. No video is stored.
 */
export function UploadDropzone() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    return () => xhrRef.current?.abort();
  }, []);

  function openPicker() {
    if (phase === "uploading" || phase === "analyzing") return;
    inputRef.current?.click();
  }

  function onFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (file.size > MAX_BYTES) {
      setPhase("error");
      setErrorMessage("That file is over 50MB. Trim the clip and try again.");
      return;
    }

    upload(file);
  }

  function upload(file: File) {
    setPhase("uploading");
    setProgress(0);
    setErrorMessage(null);

    const form = new FormData();
    form.append("file", file, file.name);

    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;
    // Post straight to the FastAPI backend. Routing through a Next.js proxy
    // would buffer the body through a Vercel serverless function, which rejects
    // payloads over ~4.5MB — and the UI allows up to 50MB. CORS is configured on
    // the backend for the Vercel origin, so a direct browser → backend POST is fine.
    xhr.open("POST", analyzeEndpoint());

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    // Once the bytes are sent, the backend is extracting pose / detecting flaws.
    xhr.upload.onload = () => setPhase("analyzing");

    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        fail(
          xhr.status >= 500
            ? "The analysis service had a problem. Please try again."
            : "We couldn't read that video. Check the guidelines and re-upload.",
        );
        return;
      }
      try {
        const result = parseAnalyzeResponse(JSON.parse(xhr.responseText));
        storeAnalysis(result);
        router.push(destinationFor(result.status));
      } catch {
        fail("We got an unexpected response. Please try again.");
      }
    };

    xhr.onerror = () =>
      fail("Network error during upload. Please try again.");
    xhr.onabort = () => setPhase("idle");

    xhr.send(form);
  }

  function fail(message: string) {
    xhrRef.current = null;
    setPhase("error");
    setErrorMessage(message);
  }

  const busy = phase === "uploading" || phase === "analyzing";

  return (
    <div className="space-y-6">
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/*"
        className="hidden"
        onChange={onFileSelected}
        data-testid="swing-file-input"
      />

      {busy ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-accent-electric/60 bg-surface-elevated p-gutter text-center">
          <p className="font-display text-lg font-bold text-on-surface-primary">
            {phase === "uploading" ? "Uploading Swing" : "Analyzing Swing"}
          </p>
          <p className="mt-1 font-mono text-data-label uppercase text-on-surface-secondary">
            {phase === "uploading"
              ? "Sending your video securely"
              : "Extracting pose & detecting flaws"}
          </p>
          <ProgressBar
            value={phase === "uploading" ? progress : undefined}
            label={phase === "uploading" ? "Uploading" : "Processing"}
            className="mt-6 w-full max-w-sm"
          />
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={openPicker}
            className="group flex min-h-[320px] w-full flex-col items-center justify-center rounded-lg border border-dashed border-on-surface-secondary bg-surface-elevated p-gutter text-center transition hover:border-accent-electric"
          >
            <span className="flex h-20 w-20 items-center justify-center rounded-lg bg-surface-overlay text-on-surface-primary transition group-hover:text-accent-electric">
              <CloudUploadIcon className="h-9 w-9" />
            </span>
            <span className="mt-6 font-display text-xl font-bold text-on-surface-primary">
              Select Swing Video
            </span>
            <span className="mt-2 font-mono text-data-label uppercase text-on-surface-secondary">
              MP4, MOV up to 50MB
            </span>
          </button>

          <button
            type="button"
            onClick={openPicker}
            className="mx-auto flex items-center justify-center gap-2 rounded border border-surface-variant px-6 py-3 font-display text-button-text text-on-surface-primary transition hover:border-on-surface-secondary"
          >
            <VideoIcon className="h-5 w-5" />
            Record New Swing
          </button>
        </>
      )}

      {phase === "error" && errorMessage ? (
        <p
          role="alert"
          className="rounded-md border border-status-error/40 bg-status-error/10 px-4 py-3 text-center font-sans text-body-md text-status-error"
        >
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
