import axios from 'axios';
import { LoginCredentials, AuthTokens } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthTokens> => {
    const response = await axios.post(`${API_BASE_URL}/auth/login/`, credentials);
    return response.data;
  },

  refreshToken: async (refresh: string): Promise<AuthTokens> => {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, { refresh });
    return response.data;
  },
};