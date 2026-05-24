import axios, { AxiosError } from 'axios';
import { Company, Experience, User, PaginatedResponse, ExperienceFilters } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
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
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && originalRequest && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true;
      
      try {
        const tokens = localStorage.getItem('auth_tokens');
        if (tokens) {
          const { refresh } = JSON.parse(tokens);
          const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, { refresh });
          const newTokens = response.data;
          
          localStorage.setItem('auth_tokens', JSON.stringify(newTokens));
          
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newTokens.access}`;
          }
          return api(originalRequest);
        }
      } catch (refreshError) {
        localStorage.removeItem('auth_tokens');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

// Companies API
export const companiesApi = {
  getAll: async (page = 1): Promise<PaginatedResponse<Company>> => {
    const response = await api.get(`/companies/?page=${page}`);
    return response.data;
  },
  
  getById: async (id: number): Promise<Company> => {
    const response = await api.get(`/companies/${id}/`);
    return response.data;
  },
  
  // Get experiences for a specific company
  getExperiences: async (
    companyId: number, 
    page = 1, 
    roundType?: 'OA' | 'INTERVIEW'
  ): Promise<PaginatedResponse<Experience>> => {
    const params = new URLSearchParams();
    params.append('company__id', companyId.toString());
    params.append('page', page.toString());
    if (roundType) {
      params.append('round_type', roundType);
    }
    
    const response = await api.get(`/experiences/?${params.toString()}`);
    return response.data;
  },
};

// Experiences API
export const experiencesApi = {
  getAll: async (filters: ExperienceFilters = {}): Promise<PaginatedResponse<Experience>> => {
    const params = new URLSearchParams();
    if (filters.company__id) params.append('company__id', filters.company__id.toString());
    if (filters.round_type) params.append('round_type', filters.round_type);
    if (filters.page) params.append('page', filters.page.toString());
    
    const response = await api.get(`/experiences/?${params.toString()}`);
    return response.data;
  },
  
  getById: async (id: number): Promise<Experience> => {
    const response = await api.get(`/experiences/${id}/`);
    return response.data;
  },
};

// Users API
export const usersApi = {
  create: async (userData: Partial<User> & { password: string }): Promise<User> => {
    const response = await api.post('/users/', userData);
    return response.data;
  },
  getById: async (id: number): Promise<User> => {
    const response = await api.get(`/users/${id}/`);
    return response.data;
  },
  update: async (id: number, userData: Partial<User> & { password?: string }): Promise<User> => {
    const response = await api.put(`/users/${id}/`, userData);
    return response.data;
  },
  patch: async (id: number, userData: Partial<User> & { password?: string }): Promise<User> => {
    const response = await api.patch(`/users/${id}/`, userData);
    return response.data;
  },
};

export default api;