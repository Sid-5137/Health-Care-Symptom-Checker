import os
import json
import re
import unicodedata
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, ValidationError
from typing import Optional
from dotenv import load_dotenv, find_dotenv
from huggingface_hub import InferenceClient
from sqlalchemy.orm import Session
try:
    # If run as a package: `python -m uvicorn backend.app:app --reload`
    from .db import SessionLocal, QueryHistory, DATABASE_URL
    from .translation import Translator
except ImportError:
    # If run from backend directory: `uvicorn app:app --reload`
    from db import SessionLocal, QueryHistory  # type: ignore
    from translation import Translator  # type: ignore
from sqlalchemy.exc import SQLAlchemyError

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

# Load environment variables from .env, regardless of where the server is started
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    # Fallback: look for .env at the project root (one level above backend/)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    candidate = os.path.join(base_dir, ".env")
    if os.path.exists(candidate):
        load_dotenv(candidate)
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-70B-Instruct")
client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    print("Initializing Hugging Face client...")
    try:
        client = InferenceClient(api_key=HF_TOKEN)
    except Exception as e:
        print(f"Failed to initialize Hugging Face InferenceClient: {e}")
        raise RuntimeError(f"Could not start the application due to client initialization failure: {e}")
    yield
    print("Cleaning up resources...")

app = FastAPI(
    title="Healthcare Symptom Checker API",
    description="An API that provides potential medical conditions based on user symptoms.",
    lifespan=lifespan
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
        if family_history and family_history.strip()
        else ""
    )
    return (
        f"A user reports the following symptoms: {symptoms}\n"
        f"{family_context}"
        "You are a healthcare-only assistant. Stay strictly on medical/symptoms context. If the user asks for unrelated topics (e.g., politics, coding), politely refuse and only provide general medical guidance relevant to the input. Never include insults, slurs, or abusive language; be neutral and respectful. Consider family history if provided to calibrate risk (e.g., earlier screening, higher suspicion), but do NOT over-index on it. Return only a JSON object with the exact keys:\n"
        '1. "probable_conditions": a list of 2–5 likely conditions (strings).\n'
        '2. "recommendations": a single string that includes:\n'
        "- 3–6 actionable next steps (plain sentences separated by semicolons),\n"
        "- red-flag symptoms that require urgent care,\n"
        "- when to seek in-person evaluation.\n"
        "3. 'next_steps': a list of 3–6 actionable next steps (as strings).\n"
        "Do not include any text outside the JSON object."
    )

# Minimal input moderation to block obvious abusive content (expanded)
ABUSE_TERMS = {
    # English common slurs/insults
    "fuck", "shit", "bitch", "bastard", "asshole", "cunt", "slut", "whore",
    # Racial/sexuality slurs (explicitly discouraged words)
    "nigger", "faggot", "retard",
}

ABUSE_PATTERNS = [
    re.compile(r"\b(kys|kill\s*yourself)\b", re.I),
    re.compile(r"\b(die\s*in\s*a\s*fire)\b", re.I),
]

def _normalize_text(text: str) -> str:
    # Normalize accents and width, collapse whitespace, and lowercase
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()

def is_offensive(text: str) -> bool:
    if not text:
        return False
    norm = _normalize_text(text)
    if any(term in norm for term in ABUSE_TERMS):
        return True
    if any(p.search(norm) for p in ABUSE_PATTERNS):
        return True
    return False

def save_query_history(db: Session, symptoms: str, response: LLMResponse):
    try:
        record = QueryHistory(
            symptoms=symptoms,
            probable_conditions="\n".join(response.probable_conditions),
            recommendations=response.recommendations
        )
        db.add(record)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        print(f"DB error during save: {e}")
        raise HTTPException(status_code=500, detail="Failed to save query history.")

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
    target_language: Optional[str] = Query(None, description="Target language code for translation (e.g., hi, ta, te, bn, ml, gu, kn, mr, pa)")
):
    if client is None:
        raise HTTPException(status_code=503, detail="Hugging Face client is not available.")

    # Reject abusive inputs early
    if is_offensive(request.symptoms or "") or is_offensive((request.family_history or "")):
        raise HTTPException(status_code=400, detail="Offensive or abusive language is not allowed.")

    prompt = build_prompt(request.symptoms, request.family_history)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Only produce a JSON object that satisfies the provided schema."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0.3,
            response_format=response_format,
        )
        llm_output_text = completion.choices[0].message.content
        llm_response_data = json.loads(llm_output_text)
        validated_response = LLMResponse(**llm_response_data)

    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Failed to parse JSON response from the model.")
    except ValidationError as e:
        raise HTTPException(status_code=502, detail=f"Invalid response structure from the model: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hugging Face API error: {e}")

    save_query_history(db, request.symptoms, validated_response)

    probable_conditions = validated_response.probable_conditions
    recommendations = validated_response.recommendations
    disclaimer = EDUCATIONAL_DISCLAIMER

    if target_language and target_language != "en":
        probable_conditions = [
            translator.translate(cond, "en", target_language) or cond for cond in probable_conditions
        ]
        recommendations = translator.translate(recommendations, "en", target_language) or recommendations
        disclaimer = translator.translate(disclaimer, "en", target_language) or disclaimer

    return SymptomResponse(
        probable_conditions=probable_conditions,
        recommendations=recommendations,
        disclaimer=disclaimer,
    )

@app.get("/health")
def health() -> dict:
    # Do not expose secrets; just return high-level info
    db_path = str(DATABASE_URL)
    # Shorten local SQLite path for display
    display_db = db_path[-80:] if len(db_path) > 80 else db_path
    return {"status": "ok", "model": MODEL_NAME, "db": display_db}
