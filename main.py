import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import WorkoutTemplate, WorkoutSession, FoodLog, FoodItem

app = FastAPI(title="Workout & Nutrition Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class IdModel(BaseModel):
    id: str


def to_public(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def read_root():
    return {"message": "Workout & Nutrition Tracker Backend Ready"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ----- Workout Templates -----
@app.post("/api/templates", response_model=IdModel)
def create_template(template: WorkoutTemplate):
    new_id = create_document("workouttemplate", template)
    return {"id": new_id}


@app.get("/api/templates")
def list_templates(q: Optional[str] = Query(None, description="Search in title/description")):
    filt = {}
    if q:
        # basic regex search for convenience
        filt = {"$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]}
    docs = get_documents("workouttemplate", filt)
    return [to_public(d) for d in docs]


# ----- Prebuilt Templates seeding -----
PREBUILT_TEMPLATES: List[WorkoutTemplate] = [
    WorkoutTemplate(
        title="Push Day (Chest/Shoulders/Triceps)",
        description="Classic push workout",
        level="Intermediate",
        exercises=[
            {"name": "Bench Press", "sets": 4, "reps": 8, "weight": None},
            {"name": "Incline Dumbbell Press", "sets": 3, "reps": 10},
            {"name": "Overhead Press", "sets": 3, "reps": 8},
            {"name": "Lateral Raise", "sets": 3, "reps": 15},
            {"name": "Tricep Pushdown", "sets": 3, "reps": 12},
        ],
    ),
    WorkoutTemplate(
        title="Pull Day (Back/Biceps)",
        description="Back and biceps focus",
        level="Intermediate",
        exercises=[
            {"name": "Deadlift", "sets": 3, "reps": 5},
            {"name": "Bent-over Row", "sets": 4, "reps": 8},
            {"name": "Lat Pulldown", "sets": 3, "reps": 10},
            {"name": "Face Pulls", "sets": 3, "reps": 15},
            {"name": "Bicep Curl", "sets": 3, "reps": 12},
        ],
    ),
    WorkoutTemplate(
        title="Leg Day",
        description="Quads, hamstrings, glutes",
        level="Intermediate",
        exercises=[
            {"name": "Squat", "sets": 4, "reps": 6},
            {"name": "Romanian Deadlift", "sets": 3, "reps": 8},
            {"name": "Leg Press", "sets": 3, "reps": 12},
            {"name": "Leg Curl", "sets": 3, "reps": 12},
            {"name": "Calf Raise", "sets": 4, "reps": 15},
        ],
    ),
]


@app.post("/api/templates/seed")
def seed_templates():
    # Only seed if collection empty
    existing = db["workouttemplate"].count_documents({}) if db else 0
    if existing == 0:
        for t in PREBUILT_TEMPLATES:
            create_document("workouttemplate", t)
        return {"seeded": len(PREBUILT_TEMPLATES)}
    return {"seeded": 0, "message": "Templates already exist"}


# ----- Workout Sessions -----
@app.post("/api/sessions", response_model=IdModel)
def create_session(session: WorkoutSession):
    new_id = create_document("workoutsession", session)
    return {"id": new_id}


@app.get("/api/sessions")
def list_sessions(user_id: str, limit: Optional[int] = Query(50, ge=1, le=200)):
    filt = {"user_id": user_id}
    docs = get_documents("workoutsession", filt, limit)
    return [to_public(d) for d in docs]


# ----- Nutrition: Food search, barcode scanning (OpenFoodFacts) -----
import requests

OPENFOODFACTS_BASE = "https://world.openfoodfacts.org"


@app.get("/api/food/search")
def search_food(q: str, page_size: int = 10):
    try:
        r = requests.get(
            f"{OPENFOODFACTS_BASE}/cgi/search.pl",
            params={
                "search_terms": q,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": page_size,
            },
            timeout=8,
        )
        data = r.json()
        products = data.get("products", [])
        results = []
        for p in products:
            nutriments = p.get("nutriments", {})
            calories = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal_serving")
            item = {
                "barcode": p.get("code"),
                "name": p.get("product_name") or p.get("generic_name") or "Unknown",
                "brand": p.get("brands"),
                "calories": float(calories) if calories is not None else 0,
                "protein": float(nutriments.get("proteins_100g", 0) or 0),
                "carbs": float(nutriments.get("carbohydrates_100g", 0) or 0),
                "fat": float(nutriments.get("fat_100g", 0) or 0),
                "serving_size": p.get("serving_size"),
            }
            results.append(item)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/food/barcode/{code}")
def food_by_barcode(code: str):
    try:
        r = requests.get(f"{OPENFOODFACTS_BASE}/api/v2/product/{code}.json", timeout=8)
        data = r.json()
        p = data.get("product") or {}
        nutriments = p.get("nutriments", {})
        calories = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal_serving")
        item = {
            "barcode": p.get("code"),
            "name": p.get("product_name") or p.get("generic_name") or "Unknown",
            "brand": p.get("brands"),
            "calories": float(calories) if calories is not None else 0,
            "protein": float(nutriments.get("proteins_100g", 0) or 0),
            "carbs": float(nutriments.get("carbohydrates_100g", 0) or 0),
            "fat": float(nutriments.get("fat_100g", 0) or 0),
            "serving_size": p.get("serving_size"),
        }
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Nutrition Logs -----
@app.post("/api/food/log", response_model=IdModel)
def create_food_log(log: FoodLog):
    new_id = create_document("foodlog", log)
    return {"id": new_id}


@app.get("/api/food/logs")
def list_food_logs(user_id: str, log_date: Optional[str] = None):
    filt = {"user_id": user_id}
    if log_date:
        filt["log_date"] = log_date  # Pydantic serializes date to ISO string
    docs = get_documents("foodlog", filt)
    return [to_public(d) for d in docs]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
