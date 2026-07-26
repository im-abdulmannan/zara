export type ProviderPreset = {
  id: string;
  label: string;
  base_url: string;
  models: string[];
  api_key_placeholder: string;
  allow_empty_key: boolean;
  default_api_key: string;
};

export type Connection = {
  provider_id: string;
  label: string;
  base_url: string;
  api_key: string;
  model: string;
  intent_enabled: boolean;
  intent_backend: string;
  intent_provider_id: string;
  intent_base_url: string;
  intent_api_key: string;
  intent_model: string;
  intent_confidence: number;
  active_summary: string;
};

export type LiveStatus = {
  state: string;
  subtitle: string;
  active_model: string;
};

export type Profile = {
  name: string;
  browser: string;
  notes: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<LiveStatus>("/api/status"),
  providers: () =>
    request<{ presets: ProviderPreset[]; saved: unknown[]; intent_models?: string[] }>(
      "/api/providers",
    ),
  connection: () => request<Connection>("/api/connection"),
  saveProvider: (body: {
    provider_id: string;
    base_url: string;
    api_key: string;
    model: string;
  }) =>
    request<Connection>("/api/provider", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  saveIntent: (body: {
    intent_enabled: boolean;
    intent_backend: string;
    intent_provider_id: string;
    intent_base_url: string;
    intent_api_key: string;
    intent_model: string;
    intent_confidence: number;
    validate_details?: boolean;
  }) =>
    request<Connection>("/api/intent", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  fetchModels: (base_url: string, api_key: string) =>
    request<{ models: string[]; free: string[] }>("/api/models/fetch", {
      method: "POST",
      body: JSON.stringify({ base_url, api_key }),
    }),
  testConnection: (base_url: string, api_key: string, model: string) =>
    request<{ reply: string }>("/api/connection/test", {
      method: "POST",
      body: JSON.stringify({ base_url, api_key, model }),
    }),
  profile: () => request<Profile>("/api/profile"),
  saveProfile: (body: Profile) =>
    request<Profile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

export function isFreeModel(modelId: string): boolean {
  const mid = modelId.trim().toLowerCase();
  if (!mid) return false;
  return (
    mid.endsWith(":free") ||
    mid.endsWith("/free") ||
    mid.includes(":free") ||
    mid.includes("/free") ||
    mid === "openrouter/free" ||
    mid === "free"
  );
}
