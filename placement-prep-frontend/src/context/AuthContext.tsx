import React, { createContext, ReactNode, useContext, useEffect, useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import { AuthState, AuthTokens, LoginCredentials, User } from '../types';
import { authApi } from '../services/auth';
import { usersApi } from '../services/api';

interface TokenClaims {
  user_id?: number;
  email?: string;
  exp: number;
}

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: true,
  });

  const fetchUser = async (claims: TokenClaims): Promise<User | null> => {
    if (!claims.user_id) return null;

    try {
      return await usersApi.getById(claims.user_id);
    } catch {
      return null;
    }
  };

  const persistSession = (tokens: AuthTokens, user: User | null) => {
    localStorage.setItem('auth_tokens', JSON.stringify(tokens));
    setState({
      user,
      tokens,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  useEffect(() => {
    const init = async () => {
      const stored = localStorage.getItem('auth_tokens');
      if (!stored) {
        setState((prev) => ({ ...prev, isLoading: false }));
        return;
      }

      try {
        const parsed: AuthTokens = JSON.parse(stored);
        let access = parsed.access;
        let refresh = parsed.refresh;

        const claims = jwtDecode<TokenClaims>(access);

        if (claims.exp * 1000 < Date.now()) {
          const refreshed = await authApi.refreshToken(refresh);
          access = refreshed.access || access;
          refresh = refreshed.refresh || refresh;
        }

        const nextTokens = { access, refresh };
        const nextClaims = jwtDecode<TokenClaims>(access);
        const user = await fetchUser(nextClaims);

        persistSession(nextTokens, user);
      } catch {
        localStorage.removeItem('auth_tokens');
        setState({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    init();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const tokens = await authApi.login(credentials);
    const claims = jwtDecode<TokenClaims>(tokens.access);
    const user = await fetchUser(claims);
    persistSession(tokens, user);
  };

  const logout = () => {
    localStorage.removeItem('auth_tokens');
    setState({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
    });
  };

  const updateUser = (user: User) => {
    setState((prev) => ({ ...prev, user }));
  };

  return <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>{children}</AuthContext.Provider>;
};
