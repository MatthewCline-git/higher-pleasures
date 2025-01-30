# Activity Tracker Bot

A Telegram bot that helps you and a friend track activities using natural language. Just message the bot with what you did, and it will automatically log the duration in a shared Google Sheets spreadsheet.

## Features

- 🤖 Natural language processing - Just tell the bot what you did in plain English
- 📊 Automatic Google Sheets tracking - Activities are logged and organized by date
- 👥 Multi-user support - Track activities for you and a friend separately
- 📅 Smart date handling - Supports relative dates ("yesterday") and explicit dates ("January 9th")
- 🔄 Activity categorization - Automatically matches similar activities to existing categories
- ⏱️ Flexible duration formats - Handles various time formats and estimates when duration isn't specified

## Setup

### Prerequisites

- Python 3.11 or higher
- Docker (optional)
- A Google Cloud project with the Sheets API enabled
- A Telegram bot token
- An OpenAI API key

### Environment Variables

Copy `.env.example` to `.env` and fill in the following:

```
SPREADSHEET_ID=""           # ID of your Google Sheets document
FRIEND_SHEET_NAME=""        # Name of your friend's sheet
MY_SHEET_NAME=""           # Name of your sheet
FRIEND_TELEGRAM_ID=""      # Your friend's Telegram user ID
MY_TELEGRAM_ID=""          # Your Telegram user ID
OPENAI_API_KEY=""          # Your OpenAI API key
TELEGRAM_BOT_API_KEY=""    # Your Telegram bot token
GOOGLE_CREDENTIALS=""      # Your Google service account credentials JSON
```

### Running with Docker

1. Build and start the container:
```bash
docker-compose up --build
```

### Running without Docker

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the bot:
```bash
python -m src.main
```

## Usage

1. Start a chat with your bot on Telegram
2. Send `/start` to get an introduction
3. Start logging activities by sending messages like:
   - "Went running for 30 minutes"
   - "Did yoga this morning for an hour"
   - "Read War and Peace for 45 mins yesterday"
   - "Meditated on January 9th for 20 minutes"

The bot will automatically:
- Parse your message to identify the activity and duration
- Match it to existing activity categories if possible
- Record it in the appropriate sheet with the correct date
- Confirm when the activity is tracked

### Commands

- `/start` - Introduction and setup
- `/help` - Show usage examples
- `/status` - Show today's activities (coming soon)

## Architecture

- `src/activities/parser.py` - Parses natural language messages using OpenAI's GPT API
- `src/activities/tracker.py` - Core activity tracking logic
- `src/sheets/client.py` - Google Sheets integration
- `src/messaging/telegram_handler.py` - Telegram bot interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - feel free to use this code for your own projects!