#!/usr/bin/env python3
"""
Habit Tracker MCP Server for Vercel Deployment
Built for #BuildWithPuch hackathon
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Annotated
from dataclasses import dataclass, asdict
from collections import defaultdict
import os
import random
import tempfile
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field

# Environment variables for Vercel
TOKEN = os.environ.get("TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Auth Provider
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# Rich Tool Description model
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

@dataclass
class Habit:
    """Represents a single habit"""
    id: str
    name: str
    description: str
    category: str
    target_frequency: str  # daily, weekly, monthly
    target_count: int  # how many times per frequency
    created_date: str
    is_active: bool = True
    streak_count: int = 0
    total_completions: int = 0

@dataclass
class HabitEntry:
    """Represents a habit completion entry"""
    habit_id: str
    date: str
    completed: bool
    notes: str = ""
    timestamp: str = ""

class HabitTracker:
    """Main habit tracking system - uses temporary storage for serverless"""
    
    def __init__(self):
        # Use temporary directory for serverless deployment
        temp_dir = tempfile.gettempdir()
        self.data_file = Path(temp_dir) / "habit_data.json"
        self.habits: Dict[str, Habit] = {}
        self.entries: List[HabitEntry] = []
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    
                # Load habits
                for habit_data in data.get('habits', []):
                    habit = Habit(**habit_data)
                    self.habits[habit.id] = habit
                
                # Load entries
                for entry_data in data.get('entries', []):
                    entry = HabitEntry(**entry_data)
                    self.entries.append(entry)
                    
            except Exception as e:
                logger.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                'habits': [asdict(habit) for habit in self.habits.values()],
                'entries': [asdict(entry) for entry in self.entries]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def create_habit(self, name: str, description: str, category: str, 
                    target_frequency: str, target_count: int) -> str:
        """Create a new habit"""
        habit_id = f"habit_{len(self.habits)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        habit = Habit(
            id=habit_id,
            name=name,
            description=description,
            category=category,
            target_frequency=target_frequency,
            target_count=target_count,
            created_date=datetime.now().isoformat()
        )
        
        self.habits[habit_id] = habit
        self.save_data()
        return habit_id
    
    def log_habit(self, habit_id: str, completed: bool, notes: str = "") -> bool:
        """Log a habit completion for today"""
        if habit_id not in self.habits:
            return False
        
        today = date.today().isoformat()
        
        # Check if already logged today
        existing_entry = next(
            (entry for entry in self.entries 
             if entry.habit_id == habit_id and entry.date == today),
            None
        )
        
        if existing_entry:
            existing_entry.completed = completed
            existing_entry.notes = notes
            existing_entry.timestamp = datetime.now().isoformat()
        else:
            entry = HabitEntry(
                habit_id=habit_id,
                date=today,
                completed=completed,
                notes=notes,
                timestamp=datetime.now().isoformat()
            )
            self.entries.append(entry)
        
        # Update habit statistics
        self._update_habit_stats(habit_id)
        self.save_data()
        return True
    
    def _update_habit_stats(self, habit_id: str):
        """Update habit statistics like streak and total completions"""
        habit = self.habits[habit_id]
        
        # Get all entries for this habit, sorted by date
        habit_entries = sorted(
            [entry for entry in self.entries if entry.habit_id == habit_id],
            key=lambda x: x.date,
            reverse=True
        )
        
        # Calculate total completions
        habit.total_completions = sum(1 for entry in habit_entries if entry.completed)
        
        # Calculate current streak
        current_streak = 0
        for entry in habit_entries:
            if entry.completed:
                current_streak += 1
            else:
                break
        
        habit.streak_count = current_streak
    
    def get_habits(self, active_only: bool = True) -> List[Dict]:
        """Get all habits"""
        habits = list(self.habits.values())
        if active_only:
            habits = [h for h in habits if h.is_active]
        
        return [asdict(habit) for habit in habits]
    
    def get_habit_progress(self, habit_id: str, days: int = 30) -> Dict:
        """Get habit progress for the last N days"""
        if habit_id not in self.habits:
            return {}
        
        habit = self.habits[habit_id]
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get entries for date range
        entries_dict = {}
        for entry in self.entries:
            if (entry.habit_id == habit_id and 
                start_date.isoformat() <= entry.date <= end_date.isoformat()):
                entries_dict[entry.date] = entry
        
        # Build progress data
        progress = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            entry = entries_dict.get(date_str)
            progress.append({
                'date': date_str,
                'completed': entry.completed if entry else False,
                'notes': entry.notes if entry else ""
            })
            current_date += timedelta(days=1)
        
        completion_rate = sum(1 for p in progress if p['completed']) / len(progress) * 100
        
        return {
            'habit': asdict(habit),
            'progress': progress,
            'completion_rate': round(completion_rate, 1),
            'total_days': len(progress),
            'completed_days': sum(1 for p in progress if p['completed'])
        }
    
    def get_analytics(self) -> Dict:
        """Get overall analytics"""
        active_habits = [h for h in self.habits.values() if h.is_active]
        
        # Category breakdown
        categories = defaultdict(int)
        for habit in active_habits:
            categories[habit.category] += 1
        
        # Today's progress
        today = date.today().isoformat()
        today_entries = [e for e in self.entries if e.date == today]
        today_completed = sum(1 for e in today_entries if e.completed)
        
        # Best streaks
        best_streaks = sorted(active_habits, key=lambda h: h.streak_count, reverse=True)[:5]
        
        return {
            'total_habits': len(active_habits),
            'categories': dict(categories),
            'today_completed': today_completed,
            'today_total': len(active_habits),
            'today_completion_rate': round(today_completed / max(len(active_habits), 1) * 100, 1),
            'best_streaks': [{'name': h.name, 'streak': h.streak_count} for h in best_streaks]
        }

# Initialize the habit tracker
habit_tracker = HabitTracker()

# Initialize MCP server
mcp = FastMCP(
    "Habit Tracker MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# Tool: validate (required by Puch)
@mcp.tool
async def validate() -> str:
    """Required validation tool for Puch AI"""
    return MY_NUMBER

# Tool: create_habit
CreateHabitDescription = RichToolDescription(
    description="Create a new habit to track with categories, frequency, and targets",
    use_when="Use when user wants to start tracking a new habit or behavior",
    side_effects="Creates a new habit entry in the system with unique ID"
)

@mcp.tool(description=CreateHabitDescription.model_dump_json())
async def create_habit(
    name: Annotated[str, Field(description="Name of the habit")],
    description: Annotated[str, Field(description="Description of the habit")],
    category: Annotated[str, Field(description="Category (e.g., health, productivity, learning)")],
    target_frequency: Annotated[str, Field(description="Target frequency: daily, weekly, or monthly")] = "daily",
    target_count: Annotated[int, Field(description="How many times per frequency period")] = 1
) -> str:
    """Create a new habit"""
    try:
        habit_id = habit_tracker.create_habit(name, description, category, target_frequency, target_count)
        return f"✅ Created habit '{name}' with ID: {habit_id}\n🎯 Ready to start tracking!"
    except Exception as e:
        return f"❌ Error creating habit: {str(e)}"

# Tool: log_habit
LogHabitDescription = RichToolDescription(
    description="Log a habit completion for today with optional notes",
    use_when="Use when user wants to record completion or non-completion of a habit",
    side_effects="Updates habit statistics including streaks and total completions"
)

@mcp.tool(description=LogHabitDescription.model_dump_json())
async def log_habit(
    habit_id: Annotated[str, Field(description="ID of the habit to log")],
    completed: Annotated[bool, Field(description="Whether the habit was completed")] = True,
    notes: Annotated[str, Field(description="Optional notes about the completion")] = ""
) -> str:
    """Log a habit completion"""
    try:
        success = habit_tracker.log_habit(habit_id, completed, notes)
        if success:
            status = "completed" if completed else "not completed"
            habit = habit_tracker.habits[habit_id]
            streak_msg = f" 🔥 Streak: {habit.streak_count} days!" if completed else ""
            return f"✅ Logged '{habit.name}' as {status} for today{streak_msg}"
        else:
            return f"❌ Habit with ID {habit_id} not found"
    except Exception as e:
        return f"❌ Error logging habit: {str(e)}"

# Tool: get_habits
GetHabitsDescription = RichToolDescription(
    description="Get all habits with current statistics and progress",
    use_when="Use when user wants to see all their habits and current status",
    side_effects="None - read-only operation"
)

@mcp.tool(description=GetHabitsDescription.model_dump_json())
async def get_habits(
    active_only: Annotated[bool, Field(description="Show only active habits")] = True
) -> str:
    """Get all habits"""
    try:
        habits = habit_tracker.get_habits(active_only)
        if not habits:
            return "🌱 No habits found. Create your first habit to get started!\n\n💡 Try: 'Create a habit for daily meditation'"
        
        result = "📋 **Your Habits:**\n\n"
        for habit in habits:
            result += f"**{habit['name']}** (ID: {habit['id']})\n"
            result += f"  📁 Category: {habit['category']}\n"
            result += f"  🎯 Target: {habit['target_count']}x {habit['target_frequency']}\n"
            result += f"  🔥 Current streak: {habit['streak_count']} days\n"
            result += f"  ✅ Total completions: {habit['total_completions']}\n"
            result += f"  📝 {habit['description']}\n\n"
        
        return result
    except Exception as e:
        return f"❌ Error getting habits: {str(e)}"

# Tool: get_habit_progress
GetProgressDescription = RichToolDescription(
    description="Get detailed progress analysis for a specific habit over time",
    use_when="Use when user wants to see detailed progress for a specific habit",
    side_effects="None - read-only operation"
)

@mcp.tool(description=GetProgressDescription.model_dump_json())
async def get_habit_progress(
    habit_id: Annotated[str, Field(description="ID of the habit")],
    days: Annotated[int, Field(description="Number of days to show progress for")] = 30
) -> str:
    """Get habit progress"""
    try:
        progress = habit_tracker.get_habit_progress(habit_id, days)
        if not progress:
            return f"❌ Habit with ID {habit_id} not found"
        
        habit = progress['habit']
        result = f"📊 **Progress for '{habit['name']}'**\n\n"
        result += f"📈 Completion Rate: {progress['completion_rate']}%\n"
        result += f"✅ Completed: {progress['completed_days']}/{progress['total_days']} days\n"
        result += f"🔥 Current Streak: {habit['streak_count']} days\n\n"
        
        result += "📅 **Recent Progress (Last 7 Days):**\n"
        recent_progress = progress['progress'][-7:]  # Last 7 days
        for day in recent_progress:
            status = "✅" if day['completed'] else "❌"
            result += f"{day['date']}: {status}"
            if day['notes']:
                result += f" - {day['notes']}"
            result += "\n"
        
        return result
    except Exception as e:
        return f"❌ Error getting progress: {str(e)}"

# Tool: get_analytics
GetAnalyticsDescription = RichToolDescription(
    description="Get overall analytics and insights across all habits",
    use_when="Use when user wants overall performance summary and insights",
    side_effects="None - read-only operation"
)

@mcp.tool(description=GetAnalyticsDescription.model_dump_json())
async def get_analytics() -> str:
    """Get analytics and insights"""
    try:
        analytics = habit_tracker.get_analytics()
        
        result = "📊 **Your Habit Analytics**\n\n"
        result += f"🎯 Total Active Habits: {analytics['total_habits']}\n"
        result += f"📈 Today's Progress: {analytics['today_completed']}/{analytics['today_total']} "
        result += f"({analytics['today_completion_rate']}%)\n\n"
        
        if analytics['categories']:
            result += "📁 **Categories:**\n"
            for category, count in analytics['categories'].items():
                result += f"  • {category.title()}: {count} habits\n"
            result += "\n"
        
        if analytics['best_streaks']:
            result += "🔥 **Top Streaks:**\n"
            for habit in analytics['best_streaks']:
                result += f"  • {habit['name']}: {habit['streak']} days\n"
        
        return result
    except Exception as e:
        return f"❌ Error getting analytics: {str(e)}"

# Tool: get_insights
GetInsightsDescription = RichToolDescription(
    description="Get AI-powered motivational insights and personalized recommendations",
    use_when="Use when user needs motivation, encouragement, or habit advice",
    side_effects="None - read-only operation"
)

@mcp.tool(description=GetInsightsDescription.model_dump_json())
async def get_insights() -> str:
    """Get motivational insights"""
    try:
        analytics = habit_tracker.get_analytics()
        habits = habit_tracker.get_habits()
        
        insights = []
        
        # Completion rate insights
        completion_rate = analytics['today_completion_rate']
        if completion_rate == 100:
            insights.append("🎉 Perfect day! You've completed all your habits today! You're unstoppable!")
        elif completion_rate >= 80:
            insights.append(f"💪 Outstanding! You're at {completion_rate}% today. You're building incredible momentum!")
        elif completion_rate >= 50:
            insights.append(f"📈 You're halfway there at {completion_rate}%! Every small step is progress worth celebrating!")
        else:
            insights.append(f"🌱 Fresh opportunities ahead! You're at {completion_rate}% - there's still time to turn today around.")
        
        # Streak insights
        best_streak = max([h['streak_count'] for h in habits], default=0)
        if best_streak >= 30:
            insights.append(f"🔥 Incredible! Your {best_streak}-day streak shows you're a true habit master!")
        elif best_streak >= 7:
            insights.append(f"✨ Your {best_streak}-day streak proves you're developing real consistency!")
        elif best_streak >= 1:
            insights.append(f"🌟 You've got a {best_streak}-day streak going - keep the momentum alive!")
        
        # Category insights
        if analytics['categories']:
            most_common = max(analytics['categories'], key=analytics['categories'].get)
            insights.append(f"🎯 You're prioritizing {most_common} habits - smart focus for maximum impact!")
        
        # Encouragement based on total habits
        total_habits = analytics['total_habits']
        if total_habits >= 5:
            insights.append("🚀 Tracking multiple habits shows serious commitment to growth - you're leveling up!")
        elif total_habits >= 1:
            insights.append("🌟 Every expert started with one habit. You're building something amazing!")
        
        # Weekly motivation
        motivational_tips = [
            "💡 Tip: Stack your habits together - do meditation right after your morning coffee!",
            "🎯 Remember: Progress beats perfection. Consistency is the real superpower!",
            "🌱 Small daily improvements lead to stunning yearly results!",
            "⚡ Your habits are votes for the person you're becoming!",
            "🏆 Champions aren't made in comfort zones - you're doing great!"
        ]
        insights.append(random.choice(motivational_tips))
        
        return "\n\n".join(insights) if insights else "🌱 Start tracking some habits to get personalized insights!"
        
    except Exception as e:
        return f"❌ Error getting insights: {str(e)}"

# Tool: get_habit_templates
GetTemplatesDescription = RichToolDescription(
    description="Get popular habit templates for quick setup",
    use_when="Use when user wants to see pre-made habit ideas they can start tracking",
    side_effects="None - read-only operation"
)

@mcp.tool(description=GetTemplatesDescription.model_dump_json())
async def get_habit_templates() -> str:
    """Get popular habit templates"""
    templates = {
        "health": [
            {"name": "Morning Workout", "description": "30-minute exercise session", "frequency": "daily"},
            {"name": "10k Steps", "description": "Walk 10,000 steps daily", "frequency": "daily"},
            {"name": "8 Hours Sleep", "description": "Get quality sleep", "frequency": "daily"},
            {"name": "Drink Water", "description": "8 glasses of water", "frequency": "daily"}
        ],
        "productivity": [
            {"name": "Deep Work", "description": "2 hours focused work", "frequency": "daily"},
            {"name": "Inbox Zero", "description": "Clear email inbox", "frequency": "daily"},
            {"name": "Weekly Review", "description": "Plan and review week", "frequency": "weekly"},
            {"name": "Learn Something New", "description": "30 minutes learning", "frequency": "daily"}
        ],
        "mindfulness": [
            {"name": "Morning Meditation", "description": "10-minute meditation", "frequency": "daily"},
            {"name": "Gratitude Journal", "description": "Write 3 things you're grateful for", "frequency": "daily"},
            {"name": "Digital Detox", "description": "1 hour without screens", "frequency": "daily"},
            {"name": "Nature Walk", "description": "15-minute outdoor walk", "frequency": "daily"}
        ],
        "learning": [
            {"name": "Read Daily", "description": "20 pages of a book", "frequency": "daily"},
            {"name": "Language Practice", "description": "15 minutes language learning", "frequency": "daily"},
            {"name": "Skill Building", "description": "Practice a skill", "frequency": "daily"},
            {"name": "Listen to Podcast", "description": "Educational podcast", "frequency": "daily"}
        ]
    }
    
    result = "🎯 **Popular Habit Templates**\n\n"
    for category, habits in templates.items():
        result += f"**{category.title()}:**\n"
        for habit in habits:
            result += f"  • {habit['name']}: {habit['description']} ({habit['frequency']})\n"
        result += "\n"
    
    result += "💡 **To use a template, say:**\n"
    result += '"Create a habit called Morning Workout in health category for daily 30-minute exercise"\n'
    result += '"Set up a Gratitude Journal habit for daily mindfulness practice"\n'
    
    return result

# Tool: get_shareable_progress
ShareProgressDescription = RichToolDescription(
    description="Generate shareable progress summary for social media",
    use_when="Use when user wants to share their habit progress achievements",
    side_effects="None - read-only operation"
)

@mcp.tool(description=ShareProgressDescription.model_dump_json())
async def get_shareable_progress() -> str:
    """Generate a shareable progress summary"""
    analytics = habit_tracker.get_analytics()
    habits = habit_tracker.get_habits()
    
    # Find best streak
    best_habit = max(habits, key=lambda h: h.get('streak_count', 0), default={})
    best_streak = best_habit.get('streak_count', 0)
    
    # Create shareable summary
    result = "🎯 **My Habit Tracking Progress** #BuildWithPuch\n\n"
    result += f"📊 Actively tracking {analytics['total_habits']} habits\n"
    result += f"🔥 Best streak: {best_streak} days"
    if best_habit:
        result += f" ({best_habit['name']})"
    result += f"\n📈 Today's completion: {analytics['today_completion_rate']}%\n"
    
    if analytics['best_streaks']:
        result += "\n🏆 **Top Performing Habits:**\n"
        for habit in analytics['best_streaks'][:3]:
            result += f"  • {habit['name']}: {habit['streak']} day streak\n"
    
    result += f"\n✨ Powered by AI-driven habit tracking!\n"
    result += "🚀 Building better habits, one day at a time!\n"
    result += "\n#HabitTracker #SelfImprovement #BuildWithPuch"
    
    return result

# Vercel handler - this is what Vercel will call
app = mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

# Run MCP Server
async def main():
    print("🚀 Starting Habit Tracker MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())