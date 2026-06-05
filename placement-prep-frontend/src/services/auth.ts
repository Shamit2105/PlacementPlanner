import axios from 'axios';
import { AuthTokens, LoginCredentials } from '../types';

const AUTH_BASE_URL = 'http://localhost:8000/api';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthTokens> => {
    const response = await axios.post(`${AUTH_BASE_URL}/token/`, credentials);
    return response.data;
  },

  refreshToken: async (refresh: string): Promise<Partial<AuthTokens>> => {
    const response = await axios.post(`${AUTH_BASE_URL}/token/refresh/`, { refresh });
    return response.data;
  },
};
