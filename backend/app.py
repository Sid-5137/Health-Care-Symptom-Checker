import os
import json
import re
import unicodedata
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import Optional
from dotenv import load_dotenv, find_dotenv
from huggingface_hub import InferenceClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Internal imports
from db import SessionLocal, QueryHistory, DATABASE_URL
from translation import Translator


class SymptomRequest(BaseModel):
    symptoms: str
    family_history: Optional[str] = None


class LLMResponse(BaseModel):
    probable_conditions: list[str]
    recommendations: str
    next_steps: list[str]


class SymptomResponse(BaseModel):
    probable_conditions: list[str]
    recommendations: str
    disclaimer: str


EDUCATIONAL_DISCLAIMER = (
    "This information is for educational purposes only and is not a substitute for "
    "professional medical advice, diagnosis, or treatment. Always consult a qualified "
    "healthcare provider with any questions you may have regarding a medical condition."
)

# Load environment variables
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)

HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-70B-Instruct")

client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    print("Initializing Hugging Face client...")
    client = InferenceClient(api_key=HF_TOKEN)
    yield
    print("Cleaning up resources...")


app = FastAPI(
    title="Healthcare Symptom Checker API",
    description="Provides possible medical conditions based on user symptoms.",
    lifespan=lifespan
)

FRONTEND_URL = os.getenv("FRONTEND_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

translator = Translator()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_prompt(symptoms: str, family_history: Optional[str] = None) -> str:
    family_context = (
        f"Known family medical history relevant to risk factors: {family_history}\n"
        if family_history else ""
    )

    return (
        f"A user reports the following symptoms: {symptoms}\n"
        f"{family_context}"
        "Return only a JSON object with:\n"
        '"probable_conditions": [...], "recommendations": "...", "next_steps": [...]\n'
    )


ABUSE_TERMS = {"fuck", "shit", "bitch", "bastard", "asshole", "cunt", "slut", "whore",
               "nigger", "faggot", "retard"}

ABUSE_PATTERNS = [
    re.compile(r"\b(kys|kill\s*yourself)\b", re.I),
    re.compile(r"\b(die\s*in\s*a\s*fire)\b", re.I),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def is_offensive(text: str) -> bool:
    if not text:
        return False
    norm = _normalize(text)
    return any(term in norm for term in ABUSE_TERMS) or any(p.search(norm) for p in ABUSE_PATTERNS)


def save_query_history(db: Session, symptoms: str, response: LLMResponse):
    try:
        record = QueryHistory(
            symptoms=symptoms,
            probable_conditions="\n".join(response.probable_conditions),
            recommendations=response.recommendations
        )
        db.add(record)
        db.commit()
    except SQLAlchemyError:
        db.rollback()


response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "LLMResponse",
        "schema": LLMResponse.model_json_schema(),
        "strict": True,
    },
}


@app.post("/check", response_model=SymptomResponse)
def check_symptoms(
    request: SymptomRequest,
    db: Session = Depends(get_db),
    target_language: Optional[str] = Query(None)
):
    if client is None:
        raise HTTPException(status_code=503, detail="Model not initialized.")

    if is_offensive(request.symptoms) or is_offensive(request.family_history or ""):
        raise HTTPException(status_code=400, detail="Offensive language detected.")

    prompt = build_prompt(request.symptoms, request.family_history)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "Return JSON only."},
                      {"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
            response_format=response_format,
        )
        response_data = json.loads(completion.choices[0].message.content)
        result = LLMResponse(**response_data)

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model Error: {e}")

    save_query_history(db, request.symptoms, result)

    conditions = result.probable_conditions
    recommendations = result.recommendations
    disclaimer = EDUCATIONAL_DISCLAIMER

    if target_language and target_language != "en":
        conditions = [translator.translate(c, "en", target_language) or c for c in conditions]
        recommendations = translator.translate(recommendations, "en", target_language) or recommendations
        disclaimer = translator.translate(disclaimer, "en", target_language) or disclaimer

    return SymptomResponse(
        probable_conditions=conditions,
        recommendations=recommendations,
        disclaimer=disclaimer,
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "db": DATABASE_URL}
