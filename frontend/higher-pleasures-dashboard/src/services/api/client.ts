import axios from "axios";
import logger from "../../utils/logger";

const apiLogger = logger.component("API");
const env_var = import.meta.env.VITE_BASE_API_URL;
console.log("env_var", env_var);
const BASE_API_URL =
  import.meta.env.VITE_BASE_API_URL || "http://localhost:8000/api/v1";
const apiClient = axios.create({
  baseURL: BASE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
});

apiClient.interceptors.request.use(
  (config) => {
    // add auth here later
    apiLogger.debug("Request", {
      method: config.method?.toUpperCase(),
      url: config.url,
    });
    return config;
  },
  (error) => {
    apiLogger.error("Request error", error);
    return Promise.reject(error);
  },
);

apiClient.interceptors.response.use(
  (response) => {
    apiLogger.debug("Response succes", {
      method: response.config.method?.toUpperCase(),
      url: response.config.url,
      status: response.status,
    });
    return response.data;
  },
  (error) => {
    // add some error handling
    apiLogger.error("Response error", {
      method: error.config?.method?.toUpperCase(),
      url: error.config?.url,
      status: error.response?.status,
      message: error.message,
    });
    return Promise.reject(error);
  },
);

export default apiClient;
