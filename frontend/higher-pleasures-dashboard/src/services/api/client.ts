import axios from "axios";
import dotenv from "dotenv";

dotenv.config();
const BASE_API_URL = process.env.BASE_API_URL;
const apiClient = axios.create({
  baseURL: BASE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  // Optional timeout
  timeout: 10000,
});

apiClient.interceptors.request.use(
  (config) => {
    // add auth here later
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

apiClient.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    // add some error handling
    console.error("API Error:", error);
    return Promise.reject(error);
  },
);

export default apiClient;
