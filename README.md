# Habit Tracker MCP Server

This is an AI-powered Habit Tracker built as an MCP (Managed Component Platform) server. It allows users to create, track, and analyze their habits through a conversational AI interface. The server is designed for easy deployment on Vercel.

This project was built for the #BuildWithPuch hackathon.

## Features

- **Create Habits**: Define new habits with names, descriptions, categories, and frequency targets.
- **Log Progress**: Record daily completions for each habit.
- **Track Streaks**: Automatically calculates and updates habit streaks.
- **View All Habits**: Get a comprehensive list of all your current habits and their stats.
- **Detailed Progress**: Analyze the progress of a specific habit over time.
- **Overall Analytics**: View a dashboard with insights across all habits.
- **Motivational Insights**: Get AI-powered encouragement and tips.
- **Habit Templates**: Browse and use pre-made templates for common habits.
- **Shareable Summaries**: Generate a social media-friendly summary of your progress.

## Tech Stack

- **Framework**: [FastMCP](https://github.com/puch-project/fastmcp) on top of FastAPI
- **Language**: Python
- **Deployment**: Vercel

## API Tools

The MCP server exposes the following tools for the AI to use:

- `validate()`: Required validation tool for the Puch AI platform.
- `create_habit(...)`: Creates a new habit.
- `log_habit(...)`: Logs a completion for a habit.
- `get_habits()`: Retrieves all active habits.
- `get_habit_progress(...)`: Gets detailed progress for one habit.
- `get_analytics()`: Returns overall analytics.
- `get_insights()`: Provides motivational feedback.
- `get_habit_templates()`: Shows a list of habit ideas.
- `get_shareable_progress()`: Creates a shareable text summary.

## Deployment to Vercel

This project is configured for seamless deployment to Vercel.

### 1. Set up your Repository

Push the code to a GitHub repository.

### 2. Import to Vercel

- Log in to your Vercel account.
- Click "Add New..." -> "Project".
- Import the GitHub repository you just created.

### 3. Configure Environment Variables

Vercel will automatically detect the `vercel.json` configuration. The final step is to add the necessary secrets.

In your Vercel project's **Settings -> Environment Variables** section, add the following:

- `TOKEN`: A secret token for authenticating with the MCP server.
- `MY_NUMBER`: The phone number required for the `validate()` tool.

### 4. Deploy

After configuring the environment variables, trigger a deployment from the Vercel dashboard. Vercel will build and deploy the server, and you'll get a public URL.

## Local Development

To run the server locally for testing:

1.  **Create a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set environment variables:**
    Create a `.env` file in the root directory and add your variables:
    ```
    TOKEN="your-secret-token"
    MY_NUMBER="your-phone-number"
    ```

4.  **Run the server:**
    The `api/main.py` file is configured to run with Uvicorn for local testing.
    ```bash
    python api/main.py
    ```
    The server will be available at `http://0.0.0.0:8086`.
