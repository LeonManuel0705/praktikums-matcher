import type { Anchor, Offer, Profile, ProviderInfo, RerankResult, SearchState, User } from "./types"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!response.ok) {
    let detail = `Fehler ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === "string") detail = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = body.detail[0].msg
    } catch {
      // Antwort ohne JSON-Körper, Standardtext bleibt stehen
    }
    throw new Error(detail)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  me: () => request<{ user: User; profile: Profile | null }>("/api/me"),
  register: (payload: Record<string, unknown>) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  saveProfile: (profile: Profile) =>
    request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(profile) }),
  providers: () =>
    request<{ providers: ProviderInfo[]; weights: Record<string, number>; rerank_available: boolean }>(
      "/api/providers",
    ),
  geoPreview: (location: string, radius: number) =>
    request<{ anchors: Anchor[] }>(
      `/api/geo/preview?location=${encodeURIComponent(location)}&radius_km=${radius}`,
    ),
  listSearches: () =>
    request<{ searches: { id: number; status: string; result_count: number }[] }>("/api/searches"),
  startSearch: (provider?: string) =>
    request<{ search_id: number; provider: string }>("/api/searches", {
      method: "POST",
      body: JSON.stringify(provider ? { provider } : {}),
    }),
  getSearch: (id: number, afterEvent = 0) =>
    request<SearchState>(`/api/searches/${id}?after_event=${afterEvent}`),
  cancelSearch: (id: number) =>
    request<{ cancelled: boolean }>(`/api/searches/${id}/cancel`, { method: "POST" }),
  rescore: (id: number) => request<{ rescored: number }>(`/api/searches/${id}/rescore`, { method: "POST" }),
  rerank: (id: number) => request<RerankResult>(`/api/searches/${id}/rerank`, { method: "POST" }),
}

export type { Offer }
