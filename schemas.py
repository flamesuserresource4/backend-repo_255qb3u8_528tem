"""
Database Schemas for Workout & Nutrition Tracker

Each Pydantic model represents a MongoDB collection. The collection name
is the lowercase of the class name (e.g., WorkoutTemplate -> "workouttemplate").
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


# --- Workout Schemas ---
class Exercise(BaseModel):
    name: str = Field(..., description="Exercise name, e.g., Bench Press")
    sets: int = Field(..., ge=1, le=20, description="Number of sets")
    reps: int = Field(..., ge=1, le=100, description="Repetitions per set")
    weight: Optional[float] = Field(None, ge=0, description="Weight per rep (kg/lb)")
    notes: Optional[str] = Field(None, description="Optional notes")

class WorkoutTemplate(BaseModel):
    title: str = Field(..., description="Template name, e.g., Push Day")
    description: Optional[str] = Field(None, description="What this workout targets")
    exercises: List[Exercise] = Field(default_factory=list)
    level: Optional[str] = Field(None, description="Beginner/Intermediate/Advanced")

class WorkoutSession(BaseModel):
    user_id: str = Field(..., description="Identifier for the user")
    session_date: date = Field(..., description="Workout date")
    title: str = Field(..., description="Session title or template used")
    exercises: List[Exercise] = Field(default_factory=list)
    notes: Optional[str] = None


# --- Nutrition Schemas ---
class FoodItem(BaseModel):
    barcode: Optional[str] = Field(None, description="UPC/EAN code if scanned")
    name: str = Field(..., description="Product name")
    brand: Optional[str] = None
    calories: float = Field(..., ge=0)
    protein: Optional[float] = Field(0, ge=0)
    carbs: Optional[float] = Field(0, ge=0)
    fat: Optional[float] = Field(0, ge=0)
    serving_size: Optional[str] = Field(None, description="Serving size label")

class FoodLog(BaseModel):
    user_id: str = Field(...)
    log_date: date = Field(..., description="Date for the log entry")
    meal: Optional[str] = Field("unspecified", description="Meal type: breakfast/lunch/dinner/snack")
    item: FoodItem
    quantity: float = Field(1.0, ge=0.1, description="Multiplier for serving size")
