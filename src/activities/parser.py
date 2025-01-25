import json
from datetime import datetime, timedelta
from openai import OpenAI

# class ActivityParser(Protocol):
#     """Protocol defining the interface for activity parsers"""

#     def parse_message(self, message: str) -> Dict[str, float]:
#         """Parse a message into activity and duration"""
#         pass


class OpenAIActivityParser:
    def __init__(self, api_key: str, confidence_threshold: float = 0.7):
        self.client = OpenAI(api_key=api_key)
        self.confidence_threshold = confidence_threshold

    def _generate_system_prompt(self, existing_activities) -> str:
        return f"""Extract activities, their durations, and dates from the message. Multiple activities may be mentioned.
Existing activity categories are: {", ".join(existing_activities)}

If a described activity closely matches an existing category, use that category.
Always convert duration to hours (e.g., 30 minutes = 0.5 hours). If there is no concrete duration number in the input, estimate.

For dates:
- For relative dates like "yesterday", "last night", return days_ago as an integer (yesterday = 1, today = 0)
- For explicit dates like "January 9th", return as "MM/DD" format
- If no date is mentioned, assume today (days_ago = 0)

Examples:
Input: "Yesterday I went for a run for 30 minutes"
Response: {{
    "activities": [
        {{
            "activity": "Running",
            "duration": 0.5,
            "confidence": 1.0,
            "matched_category": "Running",
            "days_ago": 1
        }}
    ]
}}

Input: "On January 9th I meditated for 20 minutes and did yoga for 45 minutes"
Response: {{
    "activities": [
        {{
            "activity": "Meditation",
            "duration": 0.33,
            "confidence": 0.95,
            "matched_category": "Meditation",
            "date": "01/09"
        }},
        {{
            "activity": "Yoga",
            "duration": 0.75,
            "confidence": 1.0,
            "matched_category": "Yoga",
            "date": "01/09"
        }}
    ]
}}

Input: "Last night I practiced guitar and this morning I went swimming"
Response: {{
    "activities": [
        {{
            "activity": "Guitar",
            "duration": 1.0,
            "confidence": 0.2,
            "matched_category": null,
            "days_ago": 1
        }},
        {{
            "activity": "Swimming",
            "duration": 0.5,
            "confidence": 1.0,
            "matched_category": "Swimming",
            "days_ago": 0
        }}
    ]
}}

Return JSON with an "activities" array containing objects with:
- activity: The activity name (use matched_category if confidence > {self.confidence_threshold})
- duration: Duration in hours (convert minutes to decimal hours)
- confidence: How confident (0-1) this matches an existing category
- matched_category: The existing category it matches, if any
- days_ago: Integer for relative dates (today = 0, yesterday = 1, etc.)
- date: "MM/DD" string for explicit dates (only include if an explicit date was given)"""

    def parse_message(self, message: str, existing_activities) -> list:
        """Parse a natural language message into multiple activities and durations"""
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": self._generate_system_prompt(existing_activities),
                },
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        processed_activities = []
        current_date = datetime.now().date()
        for activity_data in result["activities"]:
            if (
                activity_data.get("matched_category")
                and activity_data.get("confidence", 0) > self.confidence_threshold
            ):
                activity_data["activity"] = activity_data["matched_category"]

            if "date" in activity_data:
                month, day = map(int, activity_data["date"].split("/"))
                activity_date = current_date.replace(month=month, day=day)
            else:  # time delta
                days_ago = activity_data.get("days_ago", 0)
                activity_date = current_date - timedelta(days=days_ago)

            processed_activities.append(
                {
                    "activity": activity_data["activity"],
                    "duration": activity_data["duration"],
                    "date": activity_date.isoformat(),
                }
            )

        return processed_activities
