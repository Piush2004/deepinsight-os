"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col items-center justify-center space-y-4">
      <AlertCircle className="h-12 w-12 text-red-500" />
      <h2 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">Something went wrong!</h2>
      <p className="text-zinc-500 dark:text-zinc-400">An unexpected error has occurred.</p>
      <button
        onClick={() => reset()}
        className="mt-4 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        Try again
      </button>
    </div>
  );
}
