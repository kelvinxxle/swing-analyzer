"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CloudUploadIcon, VideoIcon } from "@/components/icons";
import { ProgressBar } from "@/components/ProgressBar";

/**
 * Static upload surface for M2. There's no real upload or analysis yet (that's
 * M3) — selecting or "recording" a video runs a simulated linear progress bar
 * and then routes to the mock results screen.
 */
export function UploadDropzone() {
  const router = useRouter();
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach(clearTimeout);
    };
  }, []);

  function startAnalysis() {
    if (analyzing) return;
    setAnalyzing(true);
    setProgress(0);

    const steps = [15, 38, 62, 85, 100];
    steps.forEach((value, i) => {
      timers.current.push(
        setTimeout(() => setProgress(value), (i + 1) * 450),
      );
    });
    timers.current.push(
      setTimeout(() => router.push("/results"), steps.length * 450 + 400),
    );
  }

  if (analyzing) {
    return (
      <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-accent-electric/60 bg-surface-elevated p-gutter text-center">
        <p className="font-display text-lg font-bold text-on-surface-primary">
          Analyzing Swing
        </p>
        <p className="mt-1 font-mono text-data-label uppercase text-on-surface-secondary">
          Extracting pose &amp; detecting flaws
        </p>
        <ProgressBar
          value={progress}
          label="Processing"
          className="mt-6 w-full max-w-sm"
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={startAnalysis}
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
        onClick={startAnalysis}
        className="mx-auto flex items-center justify-center gap-2 rounded border border-surface-variant px-6 py-3 font-display text-button-text text-on-surface-primary transition hover:border-on-surface-secondary"
      >
        <VideoIcon className="h-5 w-5" />
        Record New Swing
      </button>
    </div>
  );
}
