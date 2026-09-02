export type Interest = "ai_tech" | "business"
export type Compensation = "paid" | "unpaid" | "any"

export interface User {
  id: number
  email: string
  name: string
  school: string | null
  grade_level: string | null
}

export interface Profile {
  interests: Interest[]
  location: string
  radius_km: number
  start_date: string | null
  end_date: string | null
  compensation: Compensation
  free_text: string | null
}

export interface Criterion {
  key: string
  label: string
  weight: number
  score: number
  percent: number
  contribution: number
  detail: string
}

export interface Breakdown {
  score: number
  matched_keywords: string[]
  criteria: Criterion[]
}

export interface Offer {
  id: number
  title: string
  company: string
  city: string
  compensation_kind: "paid" | "unpaid" | "unknown"
  compensation_text: string | null
  description: string
  url: string
  source: string | null
  start_date_hint: string | null
  duration_hint: string | null
  categories: Interest[]
  target_group: string | null
  eligibility: "offen" | "nur_studierende" | "unklar"
  eligibility_reason: string | null
  evidence: string | null
  origin: string
  score: number
  breakdown: Breakdown
}

export interface SearchEvent {
  id: number
  created_at: string
  kind: string
  message: string
}

export interface SearchState {
  id: number
  status: "running" | "done" | "failed" | "cancelled"
  provider: string
  error: string | null
  events: SearchEvent[]
  results: Offer[]
}

export interface Anchor {
  name: string
  distance_km: number
  inside: boolean
  dx: number
  dy: number
}

export interface RerankResult {
  reranked: number
  note: string
}

export interface ProviderInfo {
  name: string
  label: string
  available: boolean
  live: boolean
}
