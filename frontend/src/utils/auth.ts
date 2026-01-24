import axios, { AxiosRequestConfig } from 'axios';
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;
// Get auth token
export const getAuthToken = (): string | null => {
  return localStorage.getItem('auth_token');
};

// Set auth token
export const setAuthToken = (token: string): void => {
  localStorage.setItem('auth_token', token);
};

// Remove auth token
export const removeAuthToken = (): void => {
  localStorage.removeItem('auth_token');
};

// Check if user is authenticated
export const isAuthenticated = (): boolean => {
  return !!getAuthToken();
};

// Get axios config with auth header
export const getAuthConfig = (): AxiosRequestConfig => {
  const token = getAuthToken();
  
  if (token) {
    return {
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
      }
    };
  }
  
  return {
    headers: {
      'Content-Type': 'application/json',
    }
  };
};

// Create axios instance with interceptors
export const createAuthAxios = () => {
  const instance = axios.create({
    baseURL: `${API_BASE_URL_A}/api`,
  });

  // Add token to every request
  instance.interceptors.request.use(
    (config) => {
      const token = getAuthToken();
      if (token) {
        config.headers.Authorization = `Token ${token}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Handle 401 errors
  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        removeAuthToken();
        window.location.href = '/react/loginf';
      }
      return Promise.reject(error);
    }
  );

  return instance;
};