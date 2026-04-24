import axios, { type InternalAxiosRequestConfig } from 'axios';

const baseURL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function attachBearer(config: InternalAxiosRequestConfig) {
  if (typeof window === 'undefined') return config;
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
}

// Cliente HTTP base configurado para apontar para o FastAPI local ou produção
export const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => attachBearer(config));

// Cliente específico para envio de arquivos (multipart/form-data)
export const uploadApi = axios.create({
  baseURL,
});

uploadApi.interceptors.request.use((config) => attachBearer(config));
