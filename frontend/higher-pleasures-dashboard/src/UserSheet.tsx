// src/UserSheet.tsx
import { useState, useEffect } from "react";
import { userStatsService } from "./services/api";
import { Entry } from "./services/api/dbService";
import logger from "./utils/logger";

const componentLogger = logger.component("UserSheet");

function UserSheet() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userEntries, setUserEntries] = useState<Entry[]>([]);

  useEffect(() => {
    const fetchUserStats = async () => {
      componentLogger.info("Fetching user stats");

      try {
        setLoading(true);
        const data = await userStatsService.getAllEntries();

        componentLogger.info("Fetched user stats", {
          count: data.length,
        });

        setUserEntries(data);
        setError(null);
      } catch (err) {
        componentLogger.error("Failed to fetch stats", err);
        setError("Failed to fetch stats");
      } finally {
        setLoading(false);
      }
    };

    fetchUserStats();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>User Stats</h2>
      <ul>
        {userEntries.map((entry) => (
          <li key={entry.user_activity_id}>
            <strong>User ID: {entry.user_id}</strong> - did{" "}
            {entry.user_activity_id} on{" "}
            {new Date(entry.date).toLocaleDateString()} for{" "}
            {entry.duration_minutes} minutes
            <p>Raw input: {entry.raw_input}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default UserSheet;
