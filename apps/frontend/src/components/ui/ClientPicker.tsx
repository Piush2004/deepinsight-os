"use client";

import { Building } from "lucide-react";
import type { Client } from "@/lib/api";

export function ClientPicker({
  clients,
  clientId,
  onChange,
}: {
  clients: Client[];
  clientId: string | null;
  onChange: (id: string) => void;
}) {
  if (clients.length === 0) return null;

  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
      <Building className="h-4 w-4 text-muted-foreground" />
      <select
        value={clientId ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-sm font-medium text-foreground outline-none"
        aria-label="Select client"
      >
        {clients.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </div>
  );
}
