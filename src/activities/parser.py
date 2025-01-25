import json

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
        return f"""Extract activities and their durations from the message. Multiple activities may be mentioned.
Existing activity categories are: {", ".join(existing_activities)}

If a described activity closely matches an existing category, use that category.
Always convert duration to hours (e.g., 30 minutes = 0.5 hours). If there is no concrete duration number in the input, estimate.

Examples:
Input: "Went for a run this morning for 30 minutes"
Response: {{
    "activities": [
        {{
            "activity": "Running",
            "duration": 0.5,
            "confidence": 1.0,
            "matched_category": "Running"
        }}
    ]
}}

Input: "Today I biked for an hour and read for 30 minutes"
Response: {{
    "activities": [
        {{
            "activity": "Biking",
            "duration": 1.0,
            "confidence": 0.9,
            "matched_category": "Biking"
        }},
        {{
            "activity": "Reading",
            "duration": 0.5,
            "confidence": 1.0,
            "matched_category": "Reading"
        }}
    ]
}}

Input: "Meditated for 20 minutes and did yoga for 45 minutes this morning"
Response: {{
    "activities": [
        {{
            "activity": "Meditation",
            "duration": 0.33,
            "confidence": 0.95,
            "matched_category": "Meditation"
        }},
        {{
            "activity": "Yoga",
            "duration": 0.75,
            "confidence": 1.0,
            "matched_category": "Yoga"
        }}
    ]
}}

Input: "Did calisthenics in the park and practiced piano afterwards"
Response: {{
    "activities": [
        {{
            "activity": "Calisthenics",
            "duration": 1.0,
            "confidence": 0.9,
            "matched_category": "Working out"
        }},
        {{
            "activity": "Piano",
            "duration": 0.5,
            "confidence": 0.2,
            "matched_category": null
        }}
    ]
}}

Return JSON with an "activities" array containing objects with:
- activity: The activity name (use matched_category if confidence > {self.confidence_threshold})
- duration: Duration in hours (convert minutes to decimal hours)
- confidence: How confident (0-1) this matches an existing category
- matched_category: The existing category it matches, if any"""

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
        for activity_data in result["activities"]:
            if (
                activity_data.get("matched_category")
                and activity_data.get("confidence", 0) > self.confidence_threshold
            ):
                activity_data["activity"] = activity_data["matched_category"]
                
            processed_activities.append({
                "activity": activity_data["activity"],
                "duration": activity_data["duration"],
            })
        
        return processed_activities