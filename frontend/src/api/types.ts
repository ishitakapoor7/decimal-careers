// Wire types mirroring backend/app/schemas.py. Keep these in sync with the API.

export interface Job {
  id: string;
  title: string;
  team: string;
  employment_type: string;
  seniority_level: string;
  city: string;
  state_region: string;
  country: string;
  work_mode: string;
  skills: string[];
  company: string;
  company_about: string;
  summary: string;
  about_role: string;
  responsibilities: string[];
  required_quals: string[];
  preferred_quals: string[];
  benefits: string[];
  salary_min: number;
  salary_max: number;
  posted_date: string;
}

export interface JobsPage {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface Application {
  id: string;
  candidate_id: string;
  job_id: string;
  status: string;
  created_at: string;
  name: string;
  email: string;
  earliest_start: string;
  linkedin: string;
  github: string;
  other_links: string[];
  requires_visa: boolean;
  why_company: string;
  resume_name: string;
}

// The form payload posted to /apply. name + email are required server-side.
export interface ApplyRequest {
  candidate_id: string;
  job_id: string;
  name: string;
  email: string;
  earliest_start?: string;
  linkedin?: string;
  github?: string;
  other_links?: string[];
  requires_visa?: boolean;
  why_company?: string;
  resume_name?: string;
}

export interface JobFilters {
  team?: string[];
  seniority_level?: string[];
  employment_type?: string[];
  work_mode?: string[];
  city?: string;
  state_region?: string;
  country?: string;
}
