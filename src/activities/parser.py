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
        return f"""Extract activity and duration from the message. 
Existing activity categories are: {", ".join(existing_activities)}

If the described activity closely matches an existing category, use that category.
Always convert duration to hours (e.g., 30 minutes = 0.5 hours). If there is no concrete duration number in the input, estimate.

Examples:
Input: "Went for a run this morning for 30 minutes"
Response: {{
    "activity": "Running",
    "duration": 0.5,
    "confidence": 1.0,
    "matched_category": "Running"
}}

Input: "Did some weightlifting for an hour and a half"
Response: {{
    "activity": "Working out",
    "duration": 1.5,
    "confidence": 0.9,
    "matched_category": "Working out"
}}

Input: "Read War and Peace for 45 mins"
Response: {{
    "activity": "Reading",
    "duration": 0.75,
    "confidence": 1.0,
    "matched_category": "Reading"
}}

Input: "Practiced guitar for two hours"
Response: {{
    "activity": "Guitar",
    "duration": 2.0,
    "confidence": 0.2,
    "matched_category": null
}}

Input: "Meditated before bed for twenty minutes"
Response: {{
    "activity": "Meditation",
    "duration": 0.33,
    "confidence": 0.95,
    "matched_category": "Meditation"
}}

Input: "Did calisthenics in the park this afternoon"
Response: {{
    "activity": "Calisthenics",
    "duration": 1.0,
    "confidence": 0.9,
    "matched_category": "Working out"
}}

Return JSON with:
- activity: The activity name (use matched_category if confidence > {self.confidence_threshold})
- duration: Duration in hours (convert minutes to decimal hours)
- confidence: How confident (0-1) this matches an existing category
- matched_category: The existing category it matches, if any"""

    def parse_message(self, message: str, existing_activities) -> dict:
        """Parse a natural language message into activity and duration"""
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

        if (
            result.get("matched_category")
            and result.get("confidence", 0) > self.confidence_threshold
        ):
            result["activity"] = result["matched_category"]

        return {
            "activity": result["activity"],
            "duration": result["duration"],
        }
