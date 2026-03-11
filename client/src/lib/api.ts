import axios from "axios";

export const AUTH_TOKEN_STORAGE_KEY = "streamlogic-auth-token";
export const AUTH_EXPIRED_EVENT = "streamlogic-auth-expired";

const api = axios.create({
  baseURL: "/",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      error.config?.url !== "/auth/login"
    ) {
      localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  },
);

export default api;
