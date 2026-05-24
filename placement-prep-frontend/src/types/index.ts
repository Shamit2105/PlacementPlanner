export interface Company {
  id: number;
  name: string;
  slug: string;
}

export interface Experience {
  id: number;
  company_name: string;
  round_type: 'OA' | 'INTERVIEW';
  round_type_display: string;
  target_role: string;
  batch_year: number | null;
  source_platform: string;
  source_url: string;
  extracted_dsa_questions: string[];
  extracted_core_topics: string[];
  created_at: string;
}

export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  middle_name?: string;
  profile?: {
    id: number;
    bio: string;
    target_role: string;
    batch_year: number;
  };
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ExperienceFilters {
  company__id?: number;
  round_type?: 'OA' | 'INTERVIEW';
  page?: number;
}
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}