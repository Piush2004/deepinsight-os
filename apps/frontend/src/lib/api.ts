const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

type GetToken = () => Promise<string | null>;

interface RequestOptions {
  /** Dev/demo mode only (see src/lib/demo-auth.ts) - sent as X-Demo-User, matching
   * api/core/security.py's AUTH_MODE=demo bypass. Never set outside demo mode. */
  demoUser?: string;
}

async function request<T>(
  getToken: GetToken,
  path: string,
  options: RequestInit = {},
  requestOptions: RequestOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (requestOptions.demoUser) {
    // The backend's HTTPBearer dependency still requires *some* Authorization header
    // to be present syntactically, even though AUTH_MODE=demo ignores its value.
    headers.set("Authorization", "Bearer demo");
    headers.set("X-Demo-User", requestOptions.demoUser);
  } else {
    const token = await getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export interface Client {
  id: string;
  name: string;
  industry?: string | null;
  website?: string | null;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSummary {
  id: string;
  title: string;
  reporting_period: string;
  status: string;
  created_at: string;
}

export interface ContentSummary {
  id: string;
  title: string;
  content_type: string;
  status: string;
  scheduled_date: string | null;
  created_at: string;
}

export interface IntegrationSummary {
  id: string;
  client_id: string;
  provider: string;
  status: string;
}

export interface GenerateJobResponse {
  message: string;
  client_id?: string;
  task_id?: string;
  status: "processing" | "completed" | "failed";
  result?: { status: string; report_id?: string; content_id?: string };
  error?: string;
}

export interface JobStatus {
  task_id: string;
  status: string;
  done: boolean;
  result?: { status: string; report_id?: string; content_id?: string };
  error?: string;
}

export interface SEOOpportunitySummary {
  id: string;
  opportunity_type: string;
  category: "QUICK_WIN" | "GROWTH_OPPORTUNITY" | "PERFORMANCE_RISK" | "EMERGING_MOMENTUM";
  title: string;
  source_entity: string;
  source_type: string;
  priority_score: number;
  confidence_score: number;
  impact_score: number;
  effort_estimate: string;
  status: string;
  created_at: string;
}

export interface SEOOpportunityDetail extends SEOOpportunitySummary {
  analysis_id: string;
  metrics: Record<string, number | string | null>;
  evidence: string[];
  recommended_actions: string[];
  strategic_explanation: string | null;
  evaluation_scores: Record<string, number> | null;
  approval: { status: string; comments: string | null; approver_id: string | null } | null;
  comments: Array<{ id: string; user_id: string; comment: string; created_at: string }>;
}

export interface SEOSummary {
  has_analysis: boolean;
  latest_analysis: {
    id: string;
    status: string;
    data_provider: string;
    period_start: string;
    period_end: string;
    executive_summary: string | null;
    created_at: string;
  } | null;
  category_counts: Record<"QUICK_WIN" | "GROWTH_OPPORTUNITY" | "PERFORMANCE_RISK" | "EMERGING_MOMENTUM", number>;
  total_open_opportunities: number;
}

export interface DocumentSummary {
  id: string;
  title: string;
  status: string;
  mime_type: string;
  file_size: number;
  created_at: string;
}

/** Bound to a single Clerk getToken() function so every call carries auth. Build one
 * per-render via useApiClient() - see src/hooks/useApiClient.ts. Pass demoUser only in
 * dev/demo mode (NEXT_PUBLIC_AUTH_MODE=demo, see src/lib/demo-auth.ts). */
export function createApiClient(getToken: GetToken, demoUser?: string) {
  const call = <T>(path: string, options?: RequestInit) => request<T>(getToken, path, options, { demoUser });

  return {
    clients: {
      list: (params: { q?: string; skip?: number; limit?: number } = {}) =>
        call<Client[]>(`/clients/${qs(params)}`),
      get: (clientId: string) => call<Client>(`/clients/${clientId}`),
      create: (data: { name: string; industry?: string; website?: string; description?: string }) =>
        call<Client>(`/clients/`, { method: "POST", body: JSON.stringify(data) }),
      update: (clientId: string, data: Partial<{ name: string; industry: string; website: string; description: string; status: string }>) =>
        call<Client>(`/clients/${clientId}`, { method: "PUT", body: JSON.stringify(data) }),
    },
    documents: {
      list: (clientId: string, params: { skip?: number; limit?: number } = {}) =>
        call<{ documents: DocumentSummary[] }>(`/documents${qs({ client_id: clientId, ...params })}`),
      upload: (clientId: string, file: File) => {
        const formData = new FormData();
        formData.append("client_id", clientId);
        formData.append("file", file);
        return call<{ document_id: string; status: string }>(`/documents/upload`, { method: "POST", body: formData });
      },
      get: (documentId: string) => call<Record<string, unknown>>(`/documents/${documentId}`),
      remove: (documentId: string) => call<{ message: string }>(`/documents/${documentId}`, { method: "DELETE" }),
    },
    knowledge: {
      query: (clientId: string, query: string) =>
        call<{ content: string; sources: string[]; grounded: boolean }>(
          `/knowledge/query${qs({ client_id: clientId, query })}`,
          { method: "POST" }
        ),
    },
    reports: {
      list: (clientId: string, params: { skip?: number; limit?: number } = {}) =>
        call<{ reports: ReportSummary[] }>(`/reports${qs({ client_id: clientId, ...params })}`),
      get: (reportId: string) => call<Record<string, unknown>>(`/reports/${reportId}`),
      generate: (clientId: string, reportingPeriod: string, metrics: Record<string, number>) =>
        // FastAPI embeds multiple body params under their param names when a route has
        // more than one non-scalar parameter - the wire body is {"metrics": {...},
        // "historical_metrics": null}, not the metrics dict directly.
        // status/result are populated immediately in CELERY_EAGER dev mode (the task
        // already ran synchronously by the time this responds); against a real worker,
        // status stays "processing" and result is absent until polled via jobs.get().
        call<GenerateJobResponse>(
          `/reports/generate${qs({ client_id: clientId, reporting_period: reportingPeriod })}`,
          { method: "POST", body: JSON.stringify({ metrics, historical_metrics: null }) }
        ),
      approve: (reportId: string) => call<{ message: string }>(`/reports/${reportId}/approve`, { method: "POST" }),
      reject: (reportId: string, reason: string) =>
        call<{ message: string }>(`/reports/${reportId}/reject${qs({ reason })}`, { method: "POST" }),
      comment: (reportId: string, comment: string) =>
        call<{ message: string }>(`/reports/${reportId}/comment${qs({ comment })}`, { method: "POST" }),
    },
    content: {
      list: (clientId: string, params: { content_type?: string; status?: string } = {}) =>
        call<{ content: ContentSummary[] }>(`/content${qs({ client_id: clientId, ...params })}`),
      get: (contentId: string) => call<Record<string, unknown>>(`/content/${contentId}`),
      generate: (clientId: string, contentType: string, targetAudience: string, goal: string) =>
        call<GenerateJobResponse>(
          `/content/generate${qs({ client_id: clientId, content_type: contentType, target_audience: targetAudience, goal })}`,
          { method: "POST" }
        ),
      approve: (contentId: string) => call<{ message: string }>(`/content/${contentId}/approve`, { method: "POST" }),
      reject: (contentId: string, reason: string) =>
        call<{ message: string }>(`/content/${contentId}/reject${qs({ reason })}`, { method: "POST" }),
      comment: (contentId: string, comment: string) =>
        call<{ message: string }>(`/content/${contentId}/comment${qs({ comment })}`, { method: "POST" }),
      schedule: (contentId: string, scheduledDate: string | null) =>
        call<{ message: string; scheduled_date: string | null }>(
          `/content/${contentId}/schedule${qs({ scheduled_date: scheduledDate ?? undefined })}`,
          { method: "POST" }
        ),
    },
    seo: {
      summary: (clientId: string) => call<SEOSummary>(`/seo/summary${qs({ client_id: clientId })}`),
      listOpportunities: (clientId: string, params: { category?: string; status?: string } = {}) =>
        call<{ opportunities: SEOOpportunitySummary[] }>(`/seo/opportunities${qs({ client_id: clientId, ...params })}`),
      getOpportunity: (opportunityId: string) => call<SEOOpportunityDetail>(`/seo/opportunities/${opportunityId}`),
      analyze: (clientId: string, periodStart: string, periodEnd: string) =>
        call<GenerateJobResponse>(
          `/seo/analyze${qs({ client_id: clientId, period_start: periodStart, period_end: periodEnd })}`,
          { method: "POST" }
        ),
      approve: (opportunityId: string) => call<{ message: string }>(`/seo/opportunities/${opportunityId}/approve`, { method: "POST" }),
      reject: (opportunityId: string, reason: string) =>
        call<{ message: string }>(`/seo/opportunities/${opportunityId}/reject${qs({ reason })}`, { method: "POST" }),
      comment: (opportunityId: string, comment: string) =>
        call<{ message: string }>(`/seo/opportunities/${opportunityId}/comment${qs({ comment })}`, { method: "POST" }),
      update: (opportunityId: string, data: { title?: string; recommended_actions?: string[] }) =>
        call<{ message: string }>(`/seo/opportunities/${opportunityId}${qs({ title: data.title })}`, {
          method: "PUT",
          body: data.recommended_actions ? JSON.stringify(data.recommended_actions) : undefined,
        }),
    },
    jobs: {
      get: (taskId: string) => call<JobStatus>(`/jobs/${taskId}`),
    },
    integrations: {
      list: (clientId: string) => call<{ integrations: IntegrationSummary[] }>(`/integrations/${qs({ client_id: clientId })}`),
      sync: (integrationId: string, clientId: string) =>
        call<{ status: string }>(`/integrations/${integrationId}/sync${qs({ client_id: clientId })}`, { method: "POST" }),
      disconnect: (integrationId: string, clientId: string) =>
        call<{ status: string }>(`/integrations/${integrationId}/disconnect${qs({ client_id: clientId })}`, { method: "DELETE" }),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
