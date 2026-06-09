import axios, { AxiosError } from 'axios';
import {
  Company,
  InterviewQuestion,
  InterviewSession,
  PaginatedResponse,
  QuestionCreatePayload,
  QuestionDetail,
  QuestionListItem,
  QuestionStats,
  ScrapeRequestPayload,
  SemanticSearchPayload,
  StartInterviewPayload,
  SubmitAnswerPayload,
  TaskStatusResponse,
  Topic,
  User,
  RegisterPayload,
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const tokens = localStorage.getItem('auth_tokens');
    if (tokens) {
      const { access } = JSON.parse(tokens);
      if (access) {
        config.headers.Authorization = `Bearer ${access}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true;

      const storedTokens = localStorage.getItem('auth_tokens');
      if (!storedTokens) {
        return Promise.reject(error);
      }

      try {
        const { refresh } = JSON.parse(storedTokens);
        const refreshResponse = await axios.post(`${API_BASE_URL}/token/refresh/`, { refresh });

        const nextTokens = {
          access: refreshResponse.data.access,
          refresh: refreshResponse.data.refresh || refresh,
        };

        localStorage.setItem('auth_tokens', JSON.stringify(nextTokens));

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${nextTokens.access}`;
        }

        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('auth_tokens');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const questionsApi = {
  list: async (params?: Record<string, string | number | boolean | undefined>): Promise<PaginatedResponse<QuestionListItem>> => {
    const response = await api.get('/questions/', { params });
    return response.data;
  },

  create: async (payload: QuestionCreatePayload): Promise<QuestionDetail> => {
    const response = await api.post('/questions/', payload);
    return response.data;
  },

  getById: async (id: number): Promise<QuestionDetail> => {
    const response = await api.get(`/questions/${id}/`);
    return response.data;
  },

  deleteById: async (id: number): Promise<void> => {
    await api.delete(`/questions/${id}/`);
  },

  getSimilar: async (id: number, limit = 5): Promise<{ count: number; results: QuestionListItem[] }> => {
    const response = await api.get(`/questions/${id}/similar/`, { params: { limit } });
    return response.data;
  },

  generateAnswer: async (id: number): Promise<{ message: string; answer: string }> => {
    const response = await api.post(`/questions/${id}/generate-answer/`);
    return response.data;
  },

  semanticSearch: async (payload: SemanticSearchPayload): Promise<{ count: number; results: QuestionListItem[] }> => {
    const response = await api.post('/questions/semantic-search/', payload);
    return response.data;
  },

  getStats: async (): Promise<QuestionStats> => {
    const response = await api.get('/questions/stats/');
    return response.data;
  },

  triggerScrape: async (payload: ScrapeRequestPayload): Promise<{ message: string; task_id: string; poll_url: string }> => {
    const response = await api.post('/questions/scrape/', payload);
    return response.data;
  },

  getTaskStatus: async (taskId: string): Promise<TaskStatusResponse> => {
    const response = await api.get(`/questions/tasks/${taskId}/status/`);
    return response.data;
  },
};

export const companiesApi = {
  list: async (params?: Record<string, string | number | undefined>): Promise<PaginatedResponse<Company>> => {
    const response = await api.get('/questions/companies/', { params });
    return response.data;
  },

  create: async (payload: Pick<Company, 'name' | 'slug'>): Promise<Company> => {
    const response = await api.post('/questions/companies/', payload);
    return response.data;
  },
};

export const topicsApi = {
  list: async (params?: Record<string, string | number | undefined>): Promise<PaginatedResponse<Topic>> => {
    const response = await api.get('/questions/topics/', { params });
    return response.data;
  },

  create: async (payload: Pick<Topic, 'name' | 'question_type'>): Promise<Topic> => {
    const response = await api.post('/questions/topics/', payload);
    return response.data;
  },
};

export const interviewsApi = {
  listSessions: async (): Promise<PaginatedResponse<InterviewSession>> => {
    const response = await api.get('/interviews/sessions/');
    return response.data;
  },

  startSession: async (payload: StartInterviewPayload): Promise<InterviewSession> => {
    const response = await api.post('/interviews/sessions/start/', payload);
    return response.data;
  },

  getSession: async (id: number): Promise<InterviewSession> => {
    const response = await api.get(`/interviews/sessions/${id}/`);
    return response.data;
  },

  getNextQuestion: async (id: number): Promise<InterviewQuestion | { message: string; session?: InterviewSession }> => {
    const response = await api.get(`/interviews/sessions/${id}/next_question/`);
    return response.data;
  },

  submitAnswer: async (id: number, payload: SubmitAnswerPayload): Promise<InterviewQuestion> => {
    const response = await api.post(`/interviews/sessions/${id}/submit_answer/`, payload);
    return response.data;
  },

  skipQuestion: async (id: number, questionOrder: number): Promise<InterviewQuestion> => {
    const response = await api.post(`/interviews/sessions/${id}/skip_question/`, {
      question_order: questionOrder,
    });
    return response.data;
  },

  endSession: async (id: number): Promise<InterviewSession> => {
    const response = await api.post(`/interviews/sessions/${id}/end_session/`);
    return response.data;
  },
};

export const usersApi = {
  create: async (payload: RegisterPayload): Promise<User> => {
    const response = await api.post('/users/', payload);
    return response.data;
  },

  getById: async (id: number): Promise<User> => {
    const response = await api.get(`/users/${id}/`);
    return response.data;
  },

  patch: async (id: number, payload: Partial<User> & { password?: string }): Promise<User> => {
    const response = await api.patch(`/users/${id}/`, payload);
    return response.data;
  },
};

export default api;
