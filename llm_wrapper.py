from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_SENSEI_MODEL", "qwen2.5:0.5b")
DEFAULT_OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_SENSEI_TIMEOUT", "8"))
USE_LLM_ENHANCER = os.getenv("OLLAMA_SENSEI_USE_LLM", "0").lower() in {"1", "true", "yes", "on"}
FALLBACK_OLLAMA_MODELS = [
    model.strip()
    for model in os.getenv("OLLAMA_SENSEI_FALLBACK_MODELS", "smollm2:135m,llama3.2:1b,llama3").split(",")
    if model.strip()
]

SUPPORTED_OLLAMA_MODELS = {"qwen2.5:0.5b", "smollm2:135m", "llama3.2:1b", "llama3"}

SENSEI_RULES = (
    "You are Virtual Sensei. Rewrite the provided deterministic rehab coaching "
    "message as one short spoken sentence. Preserve every clinical decision, "
    "number, risk level, readiness score, and safety instruction. Do not add "
    "diagnosis, medication advice, new exercises, prescriptions, difficulty "
    "changes, or risk-score changes."
)


def _model_candidates(requested_model: str | None) -> list[str]:
    candidates = [requested_model or DEFAULT_OLLAMA_MODEL, *FALLBACK_OLLAMA_MODELS]
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate in SUPPORTED_OLLAMA_MODELS and candidate not in unique:
            unique.append(candidate)
    return unique


def _compact_metrics(metrics: dict) -> dict:
    important_keys = (
        "Exercise",
        "ROM",
        "Previous ROM",
        "Accuracy",
        "Pain Score (0-10)",
        "Pain Score",
        "Fatigue Index (0-1)",
        "Fatigue Score",
        "Readiness Score",
        "Recovery Prediction",
        "Compensation",
    )
    compact = {key: metrics[key] for key in important_keys if key in metrics}
    return compact or dict(list(metrics.items())[:10])


def _clean_response(text: str) -> str:
    text = " ".join(text.strip().split())
    if text.startswith('"'):
        text = text[1:]
    if text.endswith('"'):
        text = text[:-1]
    for stop in (". ", "! ", "? "):
        index = text.find(stop)
        if index > 0:
            return text[: index + 1]
    return text[:220].rstrip(" ,;:")


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        text = str(value).replace("%", "").replace("degrees", "").replace("degree", "").strip()
        return float(text.split("/")[0])
    except Exception:
        return default


def generate_rule_based_coaching(metrics: dict) -> str:
    exercise = str(metrics.get("Exercise", "the exercise"))
    rom = _as_float(metrics.get("ROM", metrics.get("Current ROM", 0)))
    previous_rom = _as_float(metrics.get("Previous ROM", 0))
    accuracy = _as_float(metrics.get("Accuracy", 0))
    pain = _as_float(metrics.get("Pain Score (0-10)", metrics.get("Pain Score", 0)))
    fatigue = _as_float(metrics.get("Fatigue Score", metrics.get("Fatigue Index (0-1)", 0)))
    if fatigue <= 1:
        fatigue *= 10

    if pain >= 7:
        return "Move slowly and stay within a comfortable range today; if the pain continues, please check with your physiotherapist."
    if fatigue >= 7:
        return "You are showing signs of fatigue, so take a short rest and focus on smooth, controlled movement."
    if previous_rom > 0 and rom >= previous_rom + 3:
        return f"Excellent progress: your movement improved from {previous_rom:.0f} to {rom:.0f} degrees during {exercise}."
    if accuracy >= 80:
        return f"Great control in {exercise}; keep the same smooth pace and steady accuracy."
    if accuracy and accuracy < 55:
        return f"Focus on slower, smoother movement in {exercise}; quality matters more than speed right now."
    return f"Good work on {exercise}; continue with controlled movement and consistent practice."


def enhance_coaching_message(
    deterministic_message: str,
    metrics: dict,
    model: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """
    Optionally rewrite deterministic Virtual Sensei coaching using local Ollama.

    Environment overrides:
    - OLLAMA_HOST, default http://127.0.0.1:11434
    - OLLAMA_SENSEI_MODEL, default qwen2.5:0.5b
    - OLLAMA_SENSEI_TIMEOUT, default 8 seconds
    - OLLAMA_SENSEI_USE_LLM=1 enables optional LLM enhancement

    This function never creates rehabilitation decisions. It only receives a
    completed deterministic message and may return a communication rewrite.
    Return None when disabled, unavailable, timed out, or unsafe.
    """
    if not USE_LLM_ENHANCER:
        return None

    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    url = f"{host}/api/generate"
    request_timeout = DEFAULT_OLLAMA_TIMEOUT if timeout is None else timeout

    compact_metrics = _compact_metrics(metrics)
    user_prompt = (
        f"{SENSEI_RULES}\n"
        f"Deterministic coaching message: {deterministic_message}\n"
        "Context for tone only, not decision-making: "
        f"{json.dumps(compact_metrics, ensure_ascii=True)}"
    )

    last_error: Exception | None = None
    for model_name in _model_candidates(model):
        payload = {
            "model": model_name,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.4,
                "num_ctx": 512,
                "num_predict": 24,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as response:
                if response.status != 200:
                    continue
                result = json.loads(response.read().decode("utf-8"))
                text = _clean_response(result.get("response", ""))
                if not text:
                    continue
                if _looks_clinically_changed(deterministic_message, text):
                    print(f"[Virtual Sensei] Rejected unsafe LLM rewrite from {model_name}.")
                    continue
                if len(text.split()) < 5 or "I " in text[:12] or "I'm " in text[:16]:
                    continue
                print(f"[Virtual Sensei] Enhanced coaching language with {model_name}.")
                return text
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 404:
                print(f"[Virtual Sensei] Ollama model {model_name} is not installed. Trying fallback.")
                continue
            break
        except Exception as exc:
            last_error = exc
            break

    print(
        f"[Virtual Sensei] Local LLM unavailable ({last_error}). "
        "Using deterministic coaching."
    )
    return None


def _looks_clinically_changed(source: str, rewritten: str) -> bool:
    """Block obvious prescription/risk/safety edits in optional LLM output."""
    source_lower = source.lower()
    rewritten_lower = rewritten.lower()
    protected_terms = (
        "pain",
        "therapist",
        "difficulty",
        "readiness",
        "risk",
        "degrees",
        "/100",
        "rest",
        "slow",
        "comfortable",
    )
    for term in protected_terms:
        if term in source_lower and term not in rewritten_lower:
            return True
    blocked_terms = (
        "medication",
        "diagnose",
        "diagnosis",
        "increase difficulty",
        "decrease difficulty",
        "change your prescription",
        "ignore",
    )
    return any(term in rewritten_lower for term in blocked_terms)


def generate_llm_coaching(
    metrics: dict,
    model: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """
    Backward-compatible helper. Prefer enhance_coaching_message for new code.
    """
    deterministic_message = generate_rule_based_coaching(metrics)
    return enhance_coaching_message(deterministic_message, metrics, model, timeout) or deterministic_message
