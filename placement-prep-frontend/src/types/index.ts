export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  created_at: string;
}

export interface Topic {
  id: number;
  name: string;
  question_type: QuestionType;
}

// Legacy experience model retained for existing reusable components.
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

export type QuestionType =
  | 'DSA_CODING'
  | 'DSA_THEORY'
  | 'OS'
  | 'DBMS'
  | 'NETWORKS'
  | 'SYSTEM_DESIGN';

export type QuestionDifficulty = 'EASY' | 'MEDIUM' | 'HARD';
export type QuestionSource = 'LC' | 'GFG' | 'GENERATED';
export type ProcessingStatus = 'SCRAPED' | 'PROCESSED' | 'EMBEDDED' | 'FAILED';

export interface QuestionListItem {
  id: number;
  interview_question: string;
  answer_preview: string;
  question_type: QuestionType;
  question_type_display: string;
  difficulty: QuestionDifficulty;
  difficulty_display: string;
  source: QuestionSource;
  source_url: string;
  status: ProcessingStatus;
  is_duplicate: boolean;
  times_used: number;
  companies: Company[];
  topics: Topic[];
  created_at: string;
  similarity_score?: number;
}

export interface QuestionDetail extends Omit<QuestionListItem, 'answer_preview'> {
  interview_answer: string;
  error_log: string;
  updated_at: string;
}

export interface QuestionCreatePayload {
  question_type: QuestionType;
  difficulty: QuestionDifficulty;
  source: QuestionSource;
  source_url?: string;
  company_slugs?: string[];
  topic_ids?: number[];
}

export interface SemanticSearchPayload {
  query: string;
  question_type?: QuestionType;
  company_slug?: string;
  limit?: number;
}

export interface ScrapeRequestPayload {
  question_type?: QuestionType;
  company_name?: string;
  topic_name?: string;
  target_count?: number;
}

export interface ScrapeTaskResponse {
  message: string;
  task_id: string;
  question_type: QuestionType | '';
  scope: string;
  poll_url: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY';
  result?: unknown;
  error?: string;
}

export interface QuestionStats {
  total: number;
  unique: number;
  embedded_percent: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
}

export interface InterviewQuestion {
  id: number;
  order: number;
  question_text: string;
  question_type: QuestionType;
  difficulty: QuestionDifficulty;
  topic_tags: string;
  reference_answer: string;
  candidate_answer: string;
  score: number | null;
  verdict: string;
  feedback: string;
  strengths: string[];
  improvements: string[];
  missed_concepts: string[];
  status: 'PENDING' | 'ANSWERED' | 'EVALUATED' | 'SKIPPED';
  evaluated_at: string | null;
}

export interface InterviewSession {
  id: number;
  company: number | null;
  company_name: string;
  total_questions: number;
  questions_answered: number;
  total_score: number;
  max_possible_score: number;
  status: 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
  question_types: QuestionType[];
  questions: InterviewQuestion[];
  created_at: string;
  completed_at: string | null;
}

export interface StartInterviewPayload {
  company_slug?: string;
  question_types: QuestionType[];
  total_questions: number;
}

export interface SubmitAnswerPayload {
  question_order: number;
  candidate_answer: string;
}

export interface UserProfile {
  id: number;
  bio: string;
  target_role: string;
  batch_year: number;
}

export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  middle_name?: string;
  profile?: UserProfile;
  created_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  username: string;
  first_name: string;
  last_name: string;
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
