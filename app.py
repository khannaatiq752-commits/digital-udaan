import os
import re
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.getenv("DATABASE_PATH", "instance/digital_udaan.sqlite3"))
if not DATABASE.is_absolute():
    DATABASE = BASE_DIR / DATABASE
UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "static/uploads"))
if not UPLOAD_FOLDER.is_absolute():
    UPLOAD_FOLDER = BASE_DIR / UPLOAD_FOLDER
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO = {"mp4", "webm"}
ALLOWED_FAVICON = {"png", "ico", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-secret-before-deployment"),
    MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", "52428800")),
    UPLOAD_FOLDER=str(UPLOAD_FOLDER),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_DEBUG", "1") == "0",
)
CSRFProtect(app)
DATABASE.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

COURSE_SEEDS = [
    ("Digital Marketing Foundations", "Build a clear digital marketing plan for a small business.", "Strategy", "Beginner", 90, "Learn the channels, customer journey and a simple weekly plan.", "chart"),
    ("Instagram for Small Business", "Turn your Instagram profile into a useful customer touchpoint.", "Social Media", "Beginner", 120, "Plan content, improve your profile and measure meaningful results.", "instagram"),
    ("WhatsApp Business Essentials", "Use WhatsApp Business to serve customers and manage enquiries.", "Customer Growth", "Beginner", 75, "Set up your catalogue, quick replies and customer-friendly workflows.", "message"),
    ("SEO Basics", "Help customers discover your website through search.", "Search", "Beginner", 150, "Understand keywords, on-page SEO and local search fundamentals.", "search"),
    ("Google Business Profile", "Improve your local business presence on Google Search and Maps.", "Local Marketing", "Beginner", 60, "Create a trustworthy profile and maintain accurate business details.", "pin"),
    ("Canva Content Studio", "Design consistent marketing assets without a design team.", "Creative", "Beginner", 90, "Build reusable designs for posts, stories and promotions.", "palette"),
    ("Reels & Short-Form Video", "Plan, shoot and edit useful short videos.", "Content", "Intermediate", 120, "Create a repeatable workflow from hook to call to action.", "video"),
    ("Social Ads Fundamentals", "Understand paid social campaign structure and testing.", "Advertising", "Intermediate", 150, "Learn objectives, audiences, creative tests and budget discipline.", "target"),
    ("Marketing Analytics", "Measure results and make better marketing decisions.", "Analytics", "Beginner", 90, "Track goals, interpret simple metrics and report outcomes.", "analytics"),
    ("Build Your Online Brand", "Create a consistent, trustworthy brand presence online.", "Branding", "Beginner", 75, "Clarify your audience, message, visual system and brand voice.", "spark"),
]

LESSON_TEMPLATES = [
    ("Start with the goal", "Start by defining one customer problem and one measurable business outcome. Choose a goal such as qualified enquiries, bookings or repeat purchases.", "Write one sentence describing your target customer and the problem you solve.", "Keep the first experiment small enough to measure in a week.", "Avoid trying every platform at once.", "https://www.youtube.com/results?search_query=digital+marketing+for+small+business+beginners"),
    ("Build a simple action plan", "Pick one primary channel, create a realistic weekly publishing rhythm and give every piece of content a purpose. Record what you publish and what response it receives.", "Draft a seven-day plan with three useful posts and one customer follow-up.", "Consistency beats an ambitious plan you cannot maintain.", "Do not judge performance from one post alone.", "https://www.youtube.com/results?search_query=small+business+content+marketing+strategy"),
    ("Measure and improve", "Review the results against the goal you chose. Look for patterns, keep what works and change one variable at a time so you can learn from the outcome.", "Create a tiny report with goal, activity, result and next experiment.", "Track meaningful outcomes, not just vanity metrics.", "Do not assume correlation proves what caused a result.", "https://www.youtube.com/results?search_query=digital+marketing+analytics+beginners"),
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'student', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS courses (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE, description TEXT NOT NULL, category TEXT NOT NULL,
      level TEXT NOT NULL DEFAULT 'Beginner', duration INTEGER NOT NULL DEFAULT 60,
      outcomes TEXT NOT NULL DEFAULT '', thumbnail TEXT NOT NULL DEFAULT '',
      published INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lessons (
      id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      title TEXT NOT NULL, body TEXT NOT NULL, tips TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '', assignment TEXT NOT NULL DEFAULT '',
      video_url TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS progress (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
