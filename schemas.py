"""
Database Schemas for Creator Insight Portal

Each Pydantic model represents a MongoDB collection.
Collection name will be the lowercase of the class name.
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class Creator(BaseModel):
    name: str
    email: str
    bio: Optional[str] = None
    profileImage: Optional[str] = None
    totalPoints: int = 0

class Course(BaseModel):
    creatorId: str
    title: str
    category: str
    description: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

class Enrollment(BaseModel):
    courseId: str
    learnerId: str
    enrolledAt: Optional[datetime] = None

class Analytic(BaseModel):
    courseId: str
    timeframe: Literal['daily','weekly','monthly']
    enrollments: int
    completionRate: float = Field(ge=0, le=100)
    avgWatchTime: float = Field(description="Average watch time in minutes")
    dropOffPoints: Optional[dict] = None
    assignmentSubmissionRate: float = Field(ge=0, le=100)
    rating: float = Field(ge=0, le=5)

class Review(BaseModel):
    courseId: str
    learnerId: str
    rating: float = Field(ge=0, le=5)
    reviewText: Optional[str] = None
    createdAt: Optional[datetime] = None

class Achievement(BaseModel):
    creatorId: str
    level: Literal['Bronze','Silver','Gold','Platinum'] = 'Bronze'
    points: int = 0
    progress: float = 0.0

class AIInsight(BaseModel):
    creatorId: str
    recommendedTopic: Optional[str] = None
    summary: Optional[str] = None
    suggestions: Optional[List[str]] = None
    createdAt: Optional[datetime] = None
