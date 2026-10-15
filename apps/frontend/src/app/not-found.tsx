import Link from "next/link";
import { FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col items-center justify-center space-y-4">
      <FileQuestion className="h-12 w-12 text-zinc-400" />
      <h2 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">Page Not Found</h2>
      <p className="text-zinc-500 dark:text-zinc-400">Could not find the requested resource.</p>
      <Link
        href="/"
        className="mt-4 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        Return Home
      </Link>
    </div>
  );
}
