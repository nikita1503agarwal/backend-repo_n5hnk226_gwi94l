import os
from datetime import datetime, timedelta
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from database import db, get_documents, create_document

app = FastAPI(title="Creator Insight Portal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------- Auth (lightweight JWT-like) -------------------------
# NOTE: Minimal token implementation (demo-only). In production use PyJWT.
security = HTTPBearer(auto_error=False)

class AuthRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

FAKE_SECRET = "creator-insight-demo-secret"


def create_fake_token(email: str) -> str:
    # Very basic non-JWT token for demo purposes
    exp = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    return f"token::{email}::{exp}::{FAKE_SECRET}"


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    if not creds:
        return None
    token = creds.credentials
    try:
        parts = token.split("::")
        if len(parts) != 4:
            return None
        _, email, exp, secret = parts
        if secret != FAKE_SECRET:
            return None
        if int(exp) < int(datetime.utcnow().timestamp()):
            return None
        return email
    except Exception:
        return None


@app.post("/auth/login", response_model=TokenResponse)
def login(data: AuthRequest):
    # Accept any non-empty email/password for demo
    if not data.email or not data.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    token = create_fake_token(data.email)
    return TokenResponse(access_token=token)


# ------------------------- Schemas -------------------------
class SummaryResponse(BaseModel):
    totalCourses: int
    totalEnrollments: int
    activeLearners: int

class ActivityItem(BaseModel):
    date: str
    enrollments: int

class EnrollmentSeriesItem(BaseModel):
    label: str
    value: int

class CompletionRateResponse(BaseModel):
    completionRate: float

class WatchTimeResponse(BaseModel):
    avgWatchTime: float

class DropOffResponse(BaseModel):
    points: List[Dict[str, float]]

class AssignmentStatsResponse(BaseModel):
    submissionRate: float

class RatingResponse(BaseModel):
    rating: float
    reviewsCount: int

class ReviewItem(BaseModel):
    learnerId: str
    rating: float
    reviewText: Optional[str] = None
    createdAt: str

class CourseItem(BaseModel):
    id: str
    title: str
    category: str

class NextTopicRequest(BaseModel):
    creatorId: Optional[str] = None
    interests: Optional[List[str]] = None

class TipsRequest(BaseModel):
    courseId: str

class SummarizeReviewsRequest(BaseModel):
    courseId: str

class AITextResponse(BaseModel):
    text: str

class PortfolioRequest(BaseModel):
    creatorId: Optional[str] = None
    name: str
    bio: Optional[str] = None
    skills: Optional[List[str]] = []
    highlights: Optional[List[str]] = []

class ResumeRequest(BaseModel):
    name: str
    email: str
    summary: Optional[str] = None
    experience: Optional[List[Dict[str, Any]]] = []
    education: Optional[List[Dict[str, Any]]] = []
    skills: Optional[List[str]] = []

class AchievementLevelResponse(BaseModel):
    level: str

class ProgressResponse(BaseModel):
    points: int
    nextLevel: str
    progressPercent: float

class UpdateAchievementRequest(BaseModel):
    creatorId: str
    pointsDelta: int


# ------------------------- Helpers -------------------------

def _safe_count(collection: str, filter_dict: dict | None = None) -> int:
    try:
        return db[collection].count_documents(filter_dict or {}) if db else 0
    except Exception:
        return 0


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ------------------------- Root & Health -------------------------
@app.get("/")
def root():
    return {"name": "Creator Insight Portal API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
            response["database"] = "✅ Connected & Working"
    except Exception as e:
        response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
    return response


# ------------------------- Dashboard -------------------------
@app.get("/dashboard/summary", response_model=SummaryResponse)
def dashboard_summary(user: Optional[str] = Depends(get_current_user)):
    # Use DB counts if available, else return demo numbers
    total_courses = _safe_count("course") or 8
    total_enrollments = _safe_count("enrollment") or 1240
    active_learners = max(int(total_enrollments * 0.6), 500)
    return SummaryResponse(
        totalCourses=total_courses,
        totalEnrollments=total_enrollments,
        activeLearners=active_learners,
    )


@app.get("/dashboard/activity", response_model=List[ActivityItem])
def dashboard_activity(user: Optional[str] = Depends(get_current_user)):
    today = datetime.utcnow()
    data = []
    for i in range(14):
        d = today - timedelta(days=(13 - i))
        data.append(ActivityItem(date=d.strftime("%Y-%m-%d"), enrollments=80 + (i * 7) % 40))
    return data


# ------------------------- Courses -------------------------
@app.get("/courses", response_model=List[CourseItem])
def get_courses():
    items: List[CourseItem] = []
    try:
        docs = get_documents("course") if db else []
        for d in docs:
            items.append(CourseItem(id=str(d.get("_id")), title=d.get("title", "Untitled"), category=d.get("category", "General")))
    except Exception:
        items = []
    if not items:
        items = [
            CourseItem(id="c1", title="Mastering Python", category="Programming"),
            CourseItem(id="c2", title="Data Visualization", category="Analytics"),
            CourseItem(id="c3", title="Teaching with AI", category="Education"),
        ]
    return items


@app.get("/courses/{course_id}")
def get_course(course_id: str):
    try:
        doc = db["course"].find_one({"_id": course_id}) if db else None
    except Exception:
        doc = None
    return doc or {"id": course_id, "title": "Course", "category": "General"}


@app.get("/courses/{course_id}/enrollments")
def get_enrollments(course_id: str, period: Literal['daily','weekly','monthly'] = 'daily'):
    # Return a simple series
    length = 14 if period == 'daily' else (12 if period == 'weekly' else 6)
    series = [{"label": f"{i+1}", "value": 50 + (i * 13) % 60} for i in range(length)]
    return series


@app.get("/courses/{course_id}/completion", response_model=CompletionRateResponse)
def get_completion(course_id: str):
    return CompletionRateResponse(completionRate=82.4)


@app.get("/courses/{course_id}/watchtime", response_model=WatchTimeResponse)
def get_watch_time(course_id: str):
    return WatchTimeResponse(avgWatchTime=37.5)


@app.get("/courses/{course_id}/dropoff", response_model=DropOffResponse)
def get_dropoff(course_id: str):
    # timeline percentage vs viewers remaining
    points = [{"t": t, "v": max(0.0, 100.0 - (t * 1.2 + (5 if t > 60 else 0)))} for t in range(0, 101, 5)]
    return DropOffResponse(points=points)


@app.get("/courses/{course_id}/assignments", response_model=AssignmentStatsResponse)
def get_assignments(course_id: str):
    return AssignmentStatsResponse(submissionRate=68.0)


@app.get("/courses/{course_id}/reviews", response_model=Dict[str, Any])
def get_reviews(course_id: str):
    reviews = [
        {"learnerId": "u1", "rating": 4.5, "reviewText": "Great pacing and examples!", "createdAt": _now_iso()},
        {"learnerId": "u2", "rating": 4.8, "reviewText": "Loved the hands-on approach.", "createdAt": _now_iso()},
        {"learnerId": "u3", "rating": 4.2, "reviewText": "Clear explanations.", "createdAt": _now_iso()},
    ]
    avg = round(sum(r["rating"] for r in reviews) / len(reviews), 2)
    return {"rating": avg, "count": len(reviews), "reviews": reviews}


# ------------------------- AI Insights -------------------------
@app.post("/ai/next-topic", response_model=AITextResponse)
def ai_next_topic(body: NextTopicRequest):
    topic = "Building Interactive Dashboards with Real-time Data"
    return AITextResponse(text=f"Recommended next course topic: {topic}.")


@app.post("/ai/improvement-tips", response_model=AITextResponse)
def ai_improvement_tips(body: TipsRequest):
    tips = [
        "Shorten long lectures into 6-8 minute segments",
        "Add a recap quiz after each section",
        "Include a real-world mini project in module 3",
    ]
    return AITextResponse(text="\n".join([f"• {t}" for t in tips]))


@app.post("/ai/summarize-reviews", response_model=AITextResponse)
def ai_summarize_reviews(body: SummarizeReviewsRequest):
    return AITextResponse(text="Students appreciate clear examples and structured progression; consider more advanced challenges for fast learners.")


# ------------------------- Portfolio / Resume -------------------------
@app.post("/portfolio/generate", response_model=Dict[str, Any])
def generate_portfolio(body: PortfolioRequest):
    # Return a structured portfolio document
    return {
        "title": f"{body.name} – Creator Portfolio",
        "bio": body.bio or "Passionate educator creating impactful learning experiences.",
        "skills": body.skills or ["Curriculum Design", "Video Editing", "Python", "Data Viz"],
        "highlights": body.highlights or [
            "10,000+ learners taught",
            "Top-rated course in category",
            "95% positive reviews",
        ],
        "sections": [
            {"name": "Featured Courses", "items": ["Mastering Python", "Data Visualization"]},
            {"name": "Certifications", "items": ["AWS Certified", "Google Data Analytics"]},
        ],
    }


@app.post("/resume/generate", response_model=Dict[str, Any])
def generate_resume(body: ResumeRequest):
    return {
        "name": body.name,
        "email": body.email,
        "summary": body.summary or "Educator focused on practical, project-based learning.",
        "experience": body.experience or [
            {"role": "Course Creator", "company": "Indie", "period": "2021–Present", "details": ["Built 6 courses", "12k students"]},
        ],
        "education": body.education or [
            {"degree": "B.Sc. Computer Science", "institution": "State University"}
        ],
        "skills": body.skills or ["Python", "Teaching", "Storyboarding", "Analytics"],
    }


# ------------------------- Achievements -------------------------
@app.get("/achievements/level", response_model=AchievementLevelResponse)
def get_creator_level(creatorId: Optional[str] = None):
    points = 1860
    level = "Bronze"
    if points >= 2000:
        level = "Silver"
    if points >= 5000:
        level = "Gold"
    if points >= 10000:
        level = "Platinum"
    return AchievementLevelResponse(level=level)


@app.get("/achievements/progress", response_model=ProgressResponse)
def get_progress_to_next_level(creatorId: Optional[str] = None):
    points = 1860
    thresholds = [("Bronze", 0), ("Silver", 2000), ("Gold", 5000), ("Platinum", 10000)]
    next_level = "Silver"
    next_threshold = 2000
    for lvl, th in thresholds:
        if points < th:
            next_level = lvl
            next_threshold = th
            break
    progress = min(100.0, round(points / next_threshold * 100, 2)) if next_threshold else 100.0
    return ProgressResponse(points=points, nextLevel=next_level, progressPercent=progress)


@app.post("/achievements/update")
def update_achievements(body: UpdateAchievementRequest):
    # In a real app, update DB. Here we just echo the new points.
    return {"status": "ok", "creatorId": body.creatorId, "pointsAdded": body.pointsDelta}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
