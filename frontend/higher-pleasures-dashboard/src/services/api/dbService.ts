import apiClient from "./client";

export interface Entry {
  user_id: string;
  user_activity_id: number;
  date: Date;
  duration_minutes: number;
  raw_input: string;
}

const dbService = {
  getAllEntries: async (): Promise<Entry[]> => {
    return apiClient.get("/db/entries");
  },
  getUserEntries: async (userId: string): Promise<Entry[]> => {
    return apiClient.get(`/db/${userId}/entries`);
  },
};

export default dbService;
