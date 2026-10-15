import Link from "next/link";
import { Plug, ChevronRight } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">Settings</h1>
        <p className="text-zinc-500 dark:text-zinc-400">Manage platform settings.</p>
      </div>

      <Link
        href="/settings/integrations"
        className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900 hover:border-primary/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Plug className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="font-medium text-zinc-900 dark:text-white">Integrations</p>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Connect GA4, Search Console, and other data sources.</p>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </Link>

      <div className="rounded-xl border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-center text-sm text-zinc-500">General platform settings (billing, branding, roles) aren&apos;t built yet.</p>
      </div>
    </div>
  );
}
