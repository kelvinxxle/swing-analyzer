import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { BottomNav } from "@/components/BottomNav";
import { UploadDropzone } from "@/components/UploadDropzone";

export default function UploadPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader variant="full" />

      <main className="mx-auto flex w-full max-w-container flex-1 flex-col justify-center px-margin-mobile py-10 md:px-margin-desktop">
        <h1 className="text-center font-display text-headline-lg-mobile text-on-surface-primary">
          Upload Analysis
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-center font-sans text-body-md text-on-surface-secondary">
          One swing. One prescribed angle. Precise fixes.
        </p>

        <div className="mt-10">
          <UploadDropzone />
        </div>

        <p className="mt-10 text-center">
          <Link
            href="/error"
            className="font-mono text-data-label uppercase tracking-wider text-on-surface-secondary underline-offset-4 hover:text-status-error hover:underline"
          >
            Simulate rejection
          </Link>
        </p>
      </main>

      <BottomNav active="upload" />
    </div>
  );
}
