import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { jwtDecode } from 'jwt-decode';
import { AuthState, AuthTokens, User, LoginCredentials } from '../types';
import { authApi } from '../services/auth';
import { usersApi } from '../services/api';

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Check for existing tokens on mount
  useEffect(() => {
    const initAuth = async () => {
      const tokensStr = localStorage.getItem('auth_tokens');
      if (tokensStr) {
        try {
          const tokens: AuthTokens = JSON.parse(tokensStr);
          const decoded: any = jwtDecode(tokens.access);
          
          // Check if token is expired
          if (decoded.exp * 1000 < Date.now()) {
            // Try to refresh token
            const newTokens = await authApi.refreshToken(tokens.refresh);
            localStorage.setItem('auth_tokens', JSON.stringify(newTokens));
            
            // Fetch user data
            const user = await usersApi.getById(decoded.user_id);
            setState({
              user,
              tokens: newTokens,
              isAuthenticated: true,
              isLoading: false,
            });
          } else {
            // Token is valid, fetch user data
            const user = await usersApi.getById(decoded.user_id);
            setState({
              user,
              tokens,
              isAuthenticated: true,
              isLoading: false,
            });
          }
        } catch (error) {
          localStorage.removeItem('auth_tokens');
          setState({
            user: null,
            tokens: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } else {
        setState({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    initAuth();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const tokens = await authApi.login(credentials);
    localStorage.setItem('auth_tokens', JSON.stringify(tokens));
    
    const decoded: any = jwtDecode(tokens.access);
    const user = await usersApi.getById(decoded.user_id);
    
    setState({
      user,
      tokens,
      isAuthenticated: true,
      isLoading: false,
    });
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
    setState(prev => ({ ...prev, user }));
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};