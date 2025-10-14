"""Run raw evaluation across enabled models and test cases.

Outputs evaluation/results/raw_results.csv with columns:
model,case_id,status,raw_json

Environment:
  HF_TOKEN (for huggingface_chat types)
  BACKEND_URL (optional override for backend entries)

Usage:
  python evaluation/run_eval.py
  python evaluation/run_eval.py --output custom.csv
"""
from __future__ import annotations
import csv, json, os, argparse, datetime as dt
from pathlib import Path
from typing import Any, Dict, List
import requests, yaml

try:
    from huggingface_hub import InferenceClient  # optional
except ImportError:  # pragma: no cover
    InferenceClient = None  # type: ignore

try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore
    find_dotenv = None  # type: ignore

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
TEST_CASES_PATH = ROOT / "test_cases.json"
MODELS_PATH = ROOT / "models.yaml"
CASE_META_PATH = ROOT / "case_meta.json"  # not required here but validated exists

HF_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "EvalResponse",
        "schema": {
            "type": "object",
            "properties": {
                "probable_conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 6,
                },
                "recommendations": {"type": "string"},
                "disclaimer": {"type": "string"},
            },
            "required": ["probable_conditions", "recommendations", "disclaimer"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def load_env():
    if load_dotenv and find_dotenv:
        path = find_dotenv(usecwd=True)
        if path:
            load_dotenv(path)
        else:
            fallback = ROOT.parent / ".env"
            if fallback.exists():
                load_dotenv(fallback)


def load_test_cases() -> List[Dict[str, Any]]:
    return json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))


def load_models() -> List[Dict[str, Any]]:
    data = yaml.safe_load(MODELS_PATH.read_text(encoding="utf-8")) or {}
    models = data.get("models", [])
    return [m for m in models if m.get("enabled", True)]


def build_prompt(symptoms: str, family_history: str | None) -> str:
    family_context = (
        f"Known family medical history relevant to risk factors: {family_history}\n"
        if family_history and str(family_history).strip()
        else ""
    )
    return (
        f"A user reports the following symptoms: {symptoms}\n"
        f"{family_context}"
        "You are a healthcare-only assistant. Stay strictly on medical/symptoms context. "
        "If the user asks for unrelated topics (e.g., coding), politely refuse. Never include insults or abusive language. "
        "Consider family history if provided, but do NOT over-index on it. Return only a JSON object with the exact keys:\n"
        '1. "probable_conditions": a list of 2–5 likely conditions (strings).\n'
        '2. "recommendations": a single string with actionable steps separated by semicolons, including red-flag warnings and when to seek in-person care.\n'
        '3. "disclaimer": a short educational safety note.\n'
        "Do not include any text outside the JSON object."
    )


def call_backend(model_cfg: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    base_url = model_cfg.get("base_url") or os.getenv("BACKEND_URL", "http://localhost:8000")
    payload = {"symptoms": case["symptoms"]}
    if case.get("family_history"):
        payload["family_history"] = case["family_history"]
    params = {"target_language": case.get("language", "en")}
    r = requests.post(f"{base_url.rstrip('/')}/check", json=payload, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def call_huggingface(model_cfg: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    if InferenceClient is None:
        raise RuntimeError("huggingface_hub not installed")
    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not set")
    prompt = build_prompt(case["symptoms"], case.get("family_history"))
    client = InferenceClient(api_key=token)
    resp = client.chat.completions.create(
        model=model_cfg["model_id"],
        messages=[
            {"role": "system", "content": "Only produce a JSON object that satisfies the provided schema."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
        temperature=0.3,
        response_format=HF_RESPONSE_FORMAT,
    )
    text = resp.choices[0].message.content
    return json.loads(text)


def preflight_backend(url: str) -> bool:
    try:
        r = requests.get(f"{url.rstrip('/')}/health", timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def run(output: Path, only: List[str] | None = None):
    test_cases = load_test_cases()
    models = load_models()
    if only:
        wanted = set(only)
        models = [m for m in models if m["name"] in wanted]
        if not models:
            raise SystemExit(f"No models match --only selection: {', '.join(only)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["model", "case_id", "status", "raw_json"]
    # Preflight check for backend models to avoid noisy repeated connection errors
    for m in models:
        if m["type"] == "backend":
            base = m.get("base_url") or os.getenv("BACKEND_URL", "http://localhost:8000")
            if not preflight_backend(base):
                print(f"[warn] Backend '{m['name']}' at {base} failed health check; subsequent calls likely to error.")
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for m in models:
            for case in test_cases:
                row = {"model": m["name"], "case_id": case["id"], "status": "ok", "raw_json": ""}
                try:
                    if m["type"] == "backend":
                        result = call_backend(m, case)
                    elif m["type"].startswith("huggingface"):
                        result = call_huggingface(m, case)
                    else:
                        raise ValueError(f"Unknown model type {m['type']}")
                    row["raw_json"] = json.dumps(result, ensure_ascii=False)
                except Exception as e:  # pragma: no cover
                    row["status"] = "error"
                    row["raw_json"] = str(e)
                writer.writerow(row)
                print(f"[{row['status']}] {row['model']} :: {row['case_id']}")
    print(f"Raw results written to {output}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=None, help="Output CSV path")
    p.add_argument("--only", nargs="*", help="Subset of model names to run (space separated)")
    return p.parse_args()


def main():
    load_env()
    args = parse_args()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    default = RESULTS_DIR / f"raw_results_{ts}.csv"
    out = args.output or default
    run(out, only=args.only)


if __name__ == "__main__":
    main()
