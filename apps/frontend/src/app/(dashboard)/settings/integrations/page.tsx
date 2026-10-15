"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BarChart, Search, CheckCircle2, RefreshCw, Unplug, AlertTriangle } from "lucide-react";
import { useApiClient } from "@/hooks/useApiClient";
import { useSelectedClient } from "@/hooks/useSelectedClient";
import { ClientPicker } from "@/components/ui/ClientPicker";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/StateViews";

const KNOWN_PROVIDERS: Record<string, { name: string; icon: typeof BarChart }> = {
  ga4: { name: "Google Analytics 4", icon: BarChart },
  gsc: { name: "Google Search Console", icon: Search },
};

export default function IntegrationsPage() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  const { clientId, setClientId, clients, isLoading: clientLoading } = useSelectedClient();

  const integrationsQuery = useQuery({
    queryKey: ["integrations", clientId],
    queryFn: () => api.integrations.list(clientId as string),
    enabled: !!clientId,
  });

  const syncMutation = useMutation({
    mutationFn: (integrationId: string) => api.integrations.sync(integrationId, clientId as string),
    onSuccess: () => {
      toast.success("Sync started - this runs in the background via Celery.");
      queryClient.invalidateQueries({ queryKey: ["integrations", clientId] });
    },
    onError: (err: Error) => toast.error(`Sync failed: ${err.message}`),
  });

  const disconnectMutation = useMutation({
    mutationFn: (integrationId: string) => api.integrations.disconnect(integrationId, clientId as string),
    onSuccess: () => {
      toast.success("Disconnected");
      queryClient.invalidateQueries({ queryKey: ["integrations", clientId] });
    },
    onError: (err: Error) => toast.error(`Disconnect failed: ${err.message}`),
  });

  if (clientLoading) return <LoadingState label="Loading clients..." />;
  if (clients.length === 0) {
    return (
      <div className="max-w-6xl mx-auto">
        <EmptyState title="No clients yet" description="Create a client first to manage its integrations." />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-light tracking-tight text-foreground">Integrations</h1>
          <p className="text-muted-foreground mt-2">Connect external marketing platforms to enrich DeepInsight OS intelligence.</p>
        </div>
        <ClientPicker clients={clients} clientId={clientId} onChange={setClientId} />
      </div>

      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-700 dark:text-amber-400">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
        <p>
          OAuth for GA4/GSC is still a mocked proof-of-concept on the backend (no real Google API client wired up yet)
          - see docs/CLAUDE_CODE_AUDIT.md. Sync and Disconnect below hit real endpoints against whatever
          integrations already exist for this client.
        </p>
      </div>

      {integrationsQuery.isLoading && <LoadingState label="Loading integrations..." />}
      {integrationsQuery.isError && (
        <ErrorState message={(integrationsQuery.error as Error).message} onRetry={() => integrationsQuery.refetch()} />
      )}
      {integrationsQuery.data && integrationsQuery.data.integrations.length === 0 && (
        <EmptyState
          title="No integrations connected"
          description="Integrations are created via the OAuth connect flow, which requires real Google API credentials to be configured on the backend first."
        />
      )}

      {integrationsQuery.data && integrationsQuery.data.integrations.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {integrationsQuery.data.integrations.map((integration) => {
            const meta = KNOWN_PROVIDERS[integration.provider] ?? { name: integration.provider, icon: BarChart };
            const Icon = meta.icon;
            return (
              <div key={integration.id} className="bg-card border border-border rounded-xl p-6 shadow-sm flex flex-col">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-muted text-foreground rounded-lg">
                    <Icon className="w-5 h-5" />
                  </div>
                  <StatusBadge status={integration.status} />
                </div>

                <h3 className="text-lg font-medium text-foreground">{meta.name}</h3>

                <div className="mt-6 pt-4 border-t border-border flex justify-between items-center">
                  <button
                    onClick={() => disconnectMutation.mutate(integration.id)}
                    disabled={disconnectMutation.isPending}
                    className="text-sm text-destructive hover:opacity-80 transition-colors disabled:opacity-50"
                  >
                    Disconnect
                  </button>
                  <button
                    onClick={() => syncMutation.mutate(integration.id)}
                    disabled={syncMutation.isPending}
                    className="text-sm px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncMutation.isPending ? "animate-spin" : ""}`} />
                    Sync
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "connected") {
    return (
      <span className="flex items-center text-xs font-medium text-secondary bg-secondary/10 px-2 py-1 rounded-full">
        <CheckCircle2 className="w-3 h-3 mr-1" />
        Connected
      </span>
    );
  }
  return (
    <span className="flex items-center text-xs font-medium text-muted-foreground bg-muted px-2 py-1 rounded-full">
      <Unplug className="w-3 h-3 mr-1" />
      {status}
    </span>
  );
}
