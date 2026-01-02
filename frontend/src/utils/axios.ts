// Create a file: src/utils/axios.ts
import axios from 'axios';
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;
const axiosInstance = axios.create({
  baseURL: `${API_BASE_URL_A}/ap`,
});

// Add token to every request automatically
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default axiosInstance;