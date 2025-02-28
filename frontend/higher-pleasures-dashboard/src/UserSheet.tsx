import { useState, useEffect } from "react";
import { userStatsService } from "./services/api";
import { Entry } from "./services/api/userStats";

function UserSheet() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userEntries, setUserEntries] = useState<Entry[]>([]);

  useEffect(() => {
    const fetchUserStats = async () => {
      try {
        setLoading(true);
        const data = await userStatsService.getAllEntries();
        setUserEntries(data);
        setError(null);
      } catch (err) {
        setError("Failed to fetch stats");
        console.error(err);
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
            <strong>User ID: {entry.user_id}</strong> -
            {new Date(entry.date).toLocaleDateString()}:{entry.duration_minutes}{" "}
            minutes
            <p>Activity: {entry.raw_input}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default UserSheet;
