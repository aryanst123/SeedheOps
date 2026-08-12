import json
import logging
import re
import copy
import traceback
import time
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables (e.g. from .env file during development)
load_dotenv()

# Initialize a single reusable Google GenAI client with a 30-second timeout
api_key = os.getenv("GEMINI_API_KEY", "dummy_key_for_mock_execution")
try:
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30_000)
    )
except Exception as e:
    client = None


# Set up logging matching strict requirements: no unnecessary verbose logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("swarm_backend")

app = FastAPI(title="SeedheOps Swarm Backend", version="1.0.0")

# 1. WIDE-OPEN CORS MIDDLEWARE FOR FRONTEND COMPATIBILITY
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURABLE MODEL & SYSTEM CONSTANTS
# ==========================================

# Language configuration mapping for multilingual provider-agnostic voice settings and fallback tasks
LANGUAGE_CONFIGS = {
    "english": {
        "aliases": ["english", "en", "en-us"],
        "locale": "en-US",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "American professional female",
        "tone": "clear and authoritative",
        "energy": "medium-high",
        "formality": "professional",
        "fallback_narration": "On-call sitrep for alert '{trunc_query}': Root failure triaged. Hindsight matched historical runbook pattern from Incident #INC-8821. Hotfix execution steps sequenced and preventative risk mitigation rules staged.",
        "fallback_tasks": {
            "oom": {
                "title": "Isolate memory-leaking pod & purge volatile cache",
                "description": "kubectl drain pod-worker-3 --ignore-daemonsets -n prod && redis-cli -h cache.internal memory purge",
                "narration": "On-call sitrep for '{trunc_query}': Redis cluster memory ceiling reached. Runbook executor queued pod isolation and volatile cache eviction commands."
            },
            "deadlock": {
                "title": "Terminate blocking PostgreSQL backend transactions",
                "description": "SELECT pid, query, state FROM pg_stat_activity WHERE state = 'active' AND wait_event_type = 'Lock'; SELECT pg_terminate_backend(pid);",
                "narration": "On-call sitrep for '{trunc_query}': Database transaction deadlock identified. Terminating blocking query PIDs and resetting connection pool."
            },
            "crashloop": {
                "title": "Restart CrashLooping deployment & inspect container logs",
                "description": "kubectl logs -n prod -l app=payment-service --previous --tail=100 && kubectl rollout restart deployment/payment-service -n prod",
                "narration": "On-call sitrep for '{trunc_query}': Pod crash loop detected. Restarting deployment rollout and pulling container exit codes."
            },
            "latency": {
                "title": "Autoscale ingress gateway controllers",
                "description": "kubectl scale deployment/ingress-nginx-controller -n ingress-nginx --replicas=6 && curl -iv https://api.internal/healthz",
                "narration": "On-call sitrep for '{trunc_query}': Ingress gateway p99 latency spike mitigated by scaling controller replicas."
            },
            "cpu": {
                "title": "Increase HPA threshold & scale compute workers",
                "description": "kubectl autoscale deployment/async-worker -n prod --cpu-percent=70 --min=4 --max=16",
                "narration": "On-call sitrep for '{trunc_query}': High CPU saturation throttled. Horizontal pod autoscaler bounds increased to 16 replicas."
            },
            "ssl": {
                "title": "Trigger cert-manager TLS renewal & reload secrets",
                "description": "cmctl renew prod-wildcard-tls -n prod && kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx",
                "narration": "On-call sitrep for '{trunc_query}': TLS certificate expiration resolved. Re-issued certificate secrets to ingress controllers."
            }
        }
    },
    "hindi": {
        "aliases": ["hindi", "hi", "hi-in"],
        "locale": "hi-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Indian female",
        "tone": "clear and calm",
        "energy": "medium",
        "formality": "polite",
        "fallback_narration": "अलर्ट '{trunc_query}' के लिए ऑन-कॉल सिटरिप: समस्या का मूल कारण पहचाना गया। हिंडसाइट मेमोरी ने घटना #INC-8821 से समाधान प्राप्त किया। हॉटफिक्स रनबुक तैयार है।",
        "fallback_tasks": {
            "oom": {
                "title": "मेमोरी लीकिंग पॉड को अलग करें और कैशे साफ़ करें",
                "description": "kubectl drain pod-worker-3 --ignore-daemonsets -n prod && redis-cli -h cache.internal memory purge",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: रेडिस मेमोरी सीमा पार। पॉड आइसोलेशन और कैशे निकासी शुरू की गई।"
            },
            "deadlock": {
                "title": "अवरुद्ध पोस्टग्रेएसक्यूएल क्वेरी समाप्त करें",
                "description": "SELECT pid, query FROM pg_stat_activity WHERE wait_event_type = 'Lock'; SELECT pg_terminate_backend(pid);",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: डेटाबेस गतिरोध समाप्त किया गया और कनेक्शन पूल रीसेट किया गया।"
            },
            "crashloop": {
                "title": "क्रैश लूप डिप्लॉयमेंट को पुनः प्रारंभ करें",
                "description": "kubectl rollout restart deployment/payment-service -n prod",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: पॉड क्रैश लूप का समाधान करने के लिए डिप्लॉयमेंट रीस्टार्ट किया गया।"
            },
            "latency": {
                "title": "इनग्रेस गेटवे ऑटोस्केल करें",
                "description": "kubectl scale deployment/ingress-nginx-controller -n ingress-nginx --replicas=6",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: इनग्रेस लेटेंसी कम करने के लिए रेप्लिका बढ़ाई गईं।"
            },
            "cpu": {
                "title": "कंप्यूट वर्कर्स को ऑटोस्केल करें",
                "description": "kubectl autoscale deployment/async-worker -n prod --cpu-percent=70 --min=4 --max=16",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: उच्च सीपीयू उपयोग के लिए वर्कर्स स्केल किए गए।"
            },
            "ssl": {
                "title": "टीएलएस प्रमाणपत्र नवीनीकरण करें",
                "description": "cmctl renew prod-wildcard-tls -n prod",
                "status": "done",
                "narration": "अलर्ट '{trunc_query}' के लिए सिटरिप: टीएलएस प्रमाणपत्र सफलतापूर्वक नवीनीकृत किया गया।"
            }
        }
    },
    "hinglish": {
        "aliases": ["hinglish", "en-in", "mixed", "mixed-english-hindi"],
        "locale": "en-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Indian conversational female",
        "tone": "authoritative and clear",
        "energy": "medium-high",
        "formality": "professional",
        "fallback_narration": "On-call sitrep: Alert '{trunc_query}' triage ho gaya hai. Hindsight memory se previous fix Incident #INC-8821 retrieve karke hotfix runbook generate kar diya hai.",
        "fallback_tasks": {
            "oom": {
                "title": "Isolate memory-leaking pod & purge volatile cache",
                "description": "kubectl drain pod-worker-3 --ignore-daemonsets -n prod && redis-cli -h cache.internal memory purge",
                "narration": "On-call sitrep for '{trunc_query}': Redis cluster memory ceiling reached. Runbook executor queued pod isolation and memory eviction commands."
            },
            "deadlock": {
                "title": "Terminate blocking PostgreSQL backend transactions",
                "description": "SELECT pid, query, state FROM pg_stat_activity WHERE state = 'active' AND wait_event_type = 'Lock'; SELECT pg_terminate_backend(pid);",
                "narration": "On-call sitrep for '{trunc_query}': Database transaction deadlock identified. Terminating blocking query PIDs and resetting connection pool."
            },
            "crashloop": {
                "title": "Restart CrashLooping deployment & inspect container logs",
                "description": "kubectl logs -n prod -l app=payment-service --previous --tail=100 && kubectl rollout restart deployment/payment-service -n prod",
                "narration": "On-call sitrep for '{trunc_query}': Pod crash loop detected. Restarting deployment rollout and pulling container exit codes."
            },
            "latency": {
                "title": "Autoscale ingress gateway controllers",
                "description": "kubectl scale deployment/ingress-nginx-controller -n ingress-nginx --replicas=6 && curl -iv https://api.internal/healthz",
                "narration": "On-call sitrep for '{trunc_query}': Ingress gateway p99 latency spike mitigated by scaling controller replicas."
            },
            "cpu": {
                "title": "Increase HPA threshold & scale compute workers",
                "description": "kubectl autoscale deployment/async-worker -n prod --cpu-percent=70 --min=4 --max=16",
                "narration": "On-call sitrep for '{trunc_query}': High CPU saturation throttled. Horizontal pod autoscaler bounds increased to 16 replicas."
            },
            "ssl": {
                "title": "Trigger cert-manager TLS renewal & reload secrets",
                "description": "cmctl renew prod-wildcard-tls -n prod && kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx",
                "narration": "On-call sitrep for '{trunc_query}': TLS certificate expiration resolved. Re-issued certificate secrets to ingress controllers."
            }
        }
    },
    "tamil": {
        "aliases": ["tamil", "ta", "ta-in"],
        "locale": "ta-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "kannada": {
        "aliases": ["kannada", "kn", "kn-in"],
        "locale": "kn-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "telugu": {
        "aliases": ["telugu", "te", "te-in"],
        "locale": "te-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "malayalam": {
        "aliases": ["malayalam", "ml", "ml-in"],
        "locale": "ml-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "marathi": {
        "aliases": ["marathi", "mr", "mr-in"],
        "locale": "mr-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "gujarati": {
        "aliases": ["gujarati", "gu", "gu-in"],
        "locale": "gu-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "punjabi": {
        "aliases": ["punjabi", "pa", "pa-in"],
        "locale": "pa-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    },
    "bengali": {
        "aliases": ["bengali", "bn", "bn-in"],
        "locale": "bn-IN",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "Conversational female",
        "tone": "warm",
        "energy": "medium",
        "formality": "polite"
    }
}

# Expected agent IDs configuration
EXPECTED_AGENT_IDS = ["orchestrator", "personalization", "task-executor", "recommendation", "voice-narrator"]

# Strict DevOps Incident Response prompt instructing the model to generate dynamic components
SYSTEM_PROMPT = """You are SeedheOps, an autonomous 5-agent DevOps Incident Response Swarm. Return ONLY JSON matching this format:
{
  "traces": {
    "orchestrator": "Triage trace analyzing telemetry, root failure domain, and blast radius (20-35 words)",
    "personalization": "Hindsight Memory trace querying Vector DB (endpoint: hindsight.vectorize.io) for incident ID (e.g. #INC-8821 Retrieved from 60 days ago with Cosine Similarity: 0.942) feeding recalled runbook into Runbook Executor commands (25-40 words)",
    "task-executor": "Runbook Executor trace sequencing concrete terminal remediation steps like kubectl, redis-cli, aws-cli (20-35 words)",
    "recommendation": "Risk Mitigator trace detailing post-mortem safeguard and preventive policy (20-35 words)",
    "voice-narrator": "Audio Sitrep Agent trace summarizing the briefing for on-call SRE (20-35 words)"
  },
  "tasks": [
    {"time": "+00:00", "title": "Remediation action title", "description": "Concrete executable terminal command (e.g. kubectl ..., redis-cli ..., aws ..., psql ...)"}
  ],
  "voice_narration": "Authoritative, crisp on-call incident briefing summarizing root cause, hotfix runbook, and preventative measures",
  "language": "detected language: 'english', 'hindi', 'hinglish', 'tamil', 'kannada', 'telugu', 'malayalam', 'marathi', 'gujarati', 'punjabi', or 'bengali'",
  "language_confidence": 0.95
}
Generate 4-5 sequential remediation tasks with precise executable terminal commands in "description" and relative time offsets (+00:00, +00:02, +00:05, +00:08, +00:12). Traces must be 20-35 words each. Return ONLY valid JSON, no explanations, no markdown wrappers.

### INCIDENT ANALYSIS & DIAGNOSIS:
- Ingest infrastructure telemetry, crash logs, error codes, and outage alerts (e.g., Redis OOM kills, PostgreSQL deadlocks, Kubernetes CrashLoopBackOff, Ingress 504 timeouts, CPU throttling, TLS expirations).
- orchestrator (Triage Agent): Parse telemetry, identify root failure domain and blast radius.
- personalization (Hindsight Memory Agent): Query Hindsight vector memory store (endpoint: hindsight.vectorize.io) for past incident IDs (e.g. Incident #INC-8821 Retrieved from 60 days ago with Cosine Similarity score: 0.942) and feed recalled runbook into Runbook Executor.
- task-executor (Runbook Executor): Sequence 4-5 immediate remediation commands (e.g. kubectl, redis-cli, aws, docker, psql, systemctl).
- recommendation (Risk Mitigator): Propose long-term architectural safeguard (e.g., HPA rules, memory limits, connection pooling, circuit breakers).
- voice-narrator (Audio Sitrep Agent): Deliver an authoritative, concise situation report (sitrep) for the on-call engineer.

### NONSENSE & NON-INCIDENT PREVENTION:
- If the user query is gibberish, empty, or has no actionable infrastructure or DevOps incident context (e.g. 'asdfgh', 'banana', 'guitar'), set "tasks" to [] and "voice_narration" to: "No actionable DevOps incident telemetry detected in the prompt. Please provide error logs, stack traces, or incident descriptions.".
"""

RETRY_USER_PROMPT = "Return ONLY valid JSON. The 'voice_narration' must remain in the detected query language (English, Hindi, or Hinglish) without translating it or mixing languages. Preserve the authoritative on-call SRE sitrep tone."

# Robust default mock response for SeedheOps
DEFAULT_MOCK_RESPONSE = {
    "agents": [
        {
            "id": "orchestrator",
            "name": "Triage Agent",
            "workingStatus": "Parsing telemetry & error logs...",
            "doneStatus": "Alert triaged. Root failure identified.",
            "trace": "Telemetry ingested: Redis cluster memory ceiling reached (98.4%). Worker pod evictions detected in namespace prod-us-east-1. Routing to Hindsight Memory Agent for historical root-cause analysis."
        },
        {
            "id": "personalization",
            "name": "Hindsight Memory Agent",
            "workingStatus": "Querying Hindsight for historical incidents...",
            "doneStatus": "Historical context retrieved. Previous fix identified.",
            "trace": "Queried Hindsight Vector Database (endpoint: hindsight.vectorize.io). Vector search match: Incident #INC-8821 (Retrieved from 60 days ago) with Cosine Similarity score: 0.942. Recalled runbook payload feeds directly into Runbook Executor commands: kubectl drain, redis-cli volatile key eviction, and aws-cli ElastiCache cluster sync."
        },
        {
            "id": "task-executor",
            "name": "Runbook Executor",
            "workingStatus": "Sequencing remediation steps...",
            "doneStatus": "Immediate hotfix runbook generated.",
            "trace": "Executing runbook sequenced from #INC-8821: (1) kubectl drain failing pods, (2) redis-cli cache purge & maxmemory adjust, (3) aws-cli replica sync, (4) kubectl rollout restart deployment."
        },
        {
            "id": "recommendation",
            "name": "Risk Mitigator",
            "workingStatus": "Analyzing post-mortem risk...",
            "doneStatus": "Long-term preventative measure logged.",
            "trace": "Post-incident safeguard configured: adjust Redis maxmemory-policy to volatile-lru, increase memory request limits by 2Gi in Helm values, and configure PagerDuty threshold at 80% saturation."
        },
        {
            "id": "voice-narrator",
            "name": "Audio Sitrep Agent",
            "workingStatus": "Generating audio briefing...",
            "doneStatus": "Sitrep ready for on-call engineer.",
            "trace": "Synthesized audio sitrep for on-call SRE. Summary covers root cause, hotfix runbook execution, and long-term mitigation policies. Audio stream ready."
        }
    ],
    "tasks": [
        {
            "time": "+00:00",
            "title": "Drain & isolate failing worker pod",
            "description": "kubectl drain pod-worker-3 --ignore-daemonsets --delete-emptydir-data -n prod",
            "status": "done"
        },
        {
            "time": "+00:02",
            "title": "Evict expired volatile cache keys (#INC-8821 pattern)",
            "description": "redis-cli -h cache.internal --scan --pattern 'session:temp:*' | xargs redis-cli -h cache.internal unlink",
            "status": "done"
        },
        {
            "time": "+00:05",
            "title": "Scale Redis cluster statefulset replicas",
            "description": "kubectl scale statefulset/redis-cluster -n prod --replicas=4",
            "status": "done"
        },
        {
            "time": "+00:08",
            "title": "Sync AWS ElastiCache replica configuration",
            "description": "aws elasticache modify-replication-group --replication-group-id prod-redis-cluster --apply-immediately",
            "status": "done"
        },
        {
            "time": "+00:12",
            "title": "Verify cluster telemetry & pod health",
            "description": "kubectl get pods -n prod -l app=api-worker -w",
            "status": "done"
        }
    ],
    "voice_narration": "On-call sitrep: Redis cluster memory exhaustion detected in production. Hindsight retrieved resolution pattern from Incident #INC-8821 (Cosine similarity 0.942). Hotfix runbook sequenced: draining failing pods, purging volatile cache keys, and scaling replicas to 4. Telemetry stabilization underway.",
    "voice_settings": {
        "language": "english",
        "locale": "en-US",
        "gender": "female",
        "style": "friendly",
        "speaking_rate": 1.0,
        "pitch": 1.0,
        "voice_personality": "American professional female",
        "tone": "clear and authoritative",
        "energy": "medium-high",
        "formality": "professional"
    },
    "detected_language": {
        "language": "english",
        "confidence": 1.0,
        "source": "fallback"
    }
}

# ==========================================
# DATA TYPING SCHEMAS (UNCHANGED FOR FRONTEND COMPATIBILITY)
# ==========================================
class SwarmRequest(BaseModel):
    query: str = Field(..., description="The user query to be processed by the swarm.")

class AgentSchema(BaseModel):
    id: str = Field(..., description="Unique ID for the agent matching React config.")
    name: str = Field(..., description="Human-readable name of the agent.")
    workingStatus: str = Field(..., description="Rigid string representing the working status.")
    doneStatus: str = Field(..., description="Rigid string representing the done/completed status.")
    trace: str = Field(..., description="The detailed system/thought trace of this agent.")

class TaskSchema(BaseModel):
    time: str = Field(..., description="String representing the scheduled time slot.")
    title: str = Field(..., description="Title of the task.")
    description: str = Field(..., description="Detailed description of the task.")
    status: str = Field(..., description="Must be 'done' or a precise status string.")

class DetectedLanguageSchema(BaseModel):
    language: str = Field(..., description="The detected language name")
    confidence: Optional[float] = Field(None, description="Detection confidence score (0.0 to 1.0)")
    source: str = Field(..., description="Source of detection, either 'llm' or 'fallback'")
    script: Optional[str] = Field(None, description="Optional script identifier")
    dialect: Optional[str] = Field(None, description="Optional dialect details")
    region: Optional[str] = Field(None, description="Optional regional details")
    translation_required: Optional[bool] = Field(None, description="Whether translation is needed")

class VoiceSettingsSchema(BaseModel):
    language: str = Field(..., description="Inferred language of the narration (e.g. english, hindi, hinglish)")
    locale: str = Field(..., description="Standard voice locale (e.g. en-US, hi-IN, en-IN)")
    gender: str = Field(..., description="Preferred voice gender, e.g. female")
    style: str = Field(..., description="Speaking style, e.g. friendly")
    speaking_rate: float = Field(..., description="Preferred speaking rate, e.g. 1.0")
    pitch: float = Field(..., description="Preferred pitch, e.g. 1.0")
    language_confidence: Optional[float] = Field(None, description="Optional language detection confidence score")
    voice_personality: Optional[str] = Field(None, description="Optional voice personality description")
    tone: Optional[str] = Field(None, description="Optional expressive speaking tone")
    energy: Optional[str] = Field(None, description="Optional expressive voice energy level")
    formality: Optional[str] = Field(None, description="Optional expressive voice formality level")

class SwarmResponse(BaseModel):
    agents: List[AgentSchema]
    tasks: List[TaskSchema]
    voice_narration: str
    voice_settings: VoiceSettingsSchema
    detected_language: DetectedLanguageSchema


# ==========================================
# CORE UTILITY & PARSING FUNCTIONS
# ==========================================


def find_json_objects(text: str) -> list:
    """Finds all potential JSON object substrings in text using a brace-matching state machine.
    Respects string literals, escapes, and nesting, avoiding corrupted parsing on text/brackets in strings.
    """
    candidates = []
    n = len(text)
    in_string = False
    escape = False
    brace_depth = 0
    start_idx = -1
    
    i = 0
    while i < n:
        char = text[i]
        
        if escape:
            escape = False
            i += 1
            continue
            
        if char == '\\':
            escape = True
            i += 1
            continue
            
        if char == '"':
            in_string = not in_string
            i += 1
            continue
            
        if not in_string:
            if char == '{':
                if brace_depth == 0:
                    start_idx = i
                brace_depth += 1
            elif char == '}':
                if brace_depth > 0:
                    brace_depth -= 1
                    if brace_depth == 0 and start_idx != -1:
                        candidate = text[start_idx : i + 1]
                        candidates.append(candidate)
        i += 1
        
    return candidates

def clean_json_string(raw_str: str) -> str:
    """Extracts and returns the best valid JSON object string from a raw string.
    Optimized: Quick path check for pre-formatted JSON to bypass the parsing state machine.
    """
    if not raw_str:
        return ""
        
    # Quick Path: Check if text is already a clean JSON object (common when format='json' is used)
    cleaned = raw_str.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            json.loads(cleaned)
            return cleaned
        except Exception:
            pass
            
    # Fallback to state machine for cleaning markdown wrappers and conversational noise
    candidates = find_json_objects(raw_str)
    valid_candidates = []
    for cand in candidates:
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict):
                valid_candidates.append((cand, parsed))
        except Exception:
            continue
            
    if not valid_candidates:
        # Regex cleanup fallback
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end+1]
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass
        return raw_str
        
    # Score candidates to select the actual response data block
    best_cand_str = None
    best_score = -1
    
    for cand_str, parsed_dict in valid_candidates:
        score = 0
        # Accepts either "traces" mapping or "agents" list format
        if "traces" in parsed_dict or "agents" in parsed_dict:
            score += 4
        if "tasks" in parsed_dict:
            score += 2
            if isinstance(parsed_dict["tasks"], list):
                score += min(len(parsed_dict["tasks"]), 5)
        if "voice_narration" in parsed_dict and isinstance(parsed_dict["voice_narration"], str) and parsed_dict["voice_narration"].strip():
            score += 5
            
        if score > best_score:
            best_score = score
            best_cand_str = cand_str
            
    return best_cand_str or valid_candidates[0][0]

def normalize_language(lang_str: str) -> str:
    """Normalize language value matching standard name variations or aliases to canonical names."""
    if not lang_str:
        return "english"
    cleaned = str(lang_str).strip().lower()
    for canonical_key, config in LANGUAGE_CONFIGS.items():
        if cleaned == canonical_key:
            return canonical_key
        aliases = config.get("aliases", [])
        if cleaned in [a.lower() for a in aliases]:
            return canonical_key
            
    # Substring matching fallback
    for canonical_key, config in LANGUAGE_CONFIGS.items():
        if canonical_key in cleaned:
            return canonical_key
        aliases = config.get("aliases", [])
        for alias in aliases:
            if alias.lower() in cleaned:
                return canonical_key
                
    return cleaned

def infer_language_from_text(text: str) -> str:
    """Helper to detect language based on character patterns and common words for fallback/repair."""
    if not text:
        return "english"
    # Devanagari Unicode block check for Hindi
    if re.search(r"[\u0900-\u097F]", text):
        return "hindi"
        
    lower_text = text.lower()
    
    # Common Hinglish indicators (colloquial words, mixed Hindi terms in Latin script)
    hinglish_keywords = [
        "kal", "aaj", "karna", "krna", "hai", "tha", "rahega", "hoga", "bana", "banao", 
        "yaar", "bro", "gym", "office", "khana", "jaana", "jana", "lena", "krdo", "kardo", 
        "hona", "chahiye", "ho", "gaya", "kya", "bhai", "sab", "toh", "ko", "se", "aur", "pe"
    ]
    
    words = re.findall(r"\b[a-z]+\b", lower_text)
    if not words:
        return "english"
        
    # Count how many words are common Hinglish/Hindi Romanized terms
    hinglish_word_count = sum(1 for w in words if w in hinglish_keywords)
    
    if hinglish_word_count > 0:
        return "hinglish"
        
    return "english"

def repair_and_build_response(data: dict) -> dict:
    """Repairs partial responses and constructs the final SwarmResponse structure.
    Saves token generation overhead by populating static agent profiles in python.
    """
    if not isinstance(data, dict):
        return None
        
    default_ref = DEFAULT_MOCK_RESPONSE
    
    # 1. Resolve voice narration
    voice_narration = data.get("voice_narration")
    if not isinstance(voice_narration, str) or not voice_narration.strip():
        voice_narration = default_ref["voice_narration"]
        
    # 2. Resolve language detection
    raw_lang = data.get("language")
    if not raw_lang and isinstance(data.get("voice_settings"), dict):
        raw_lang = data["voice_settings"].get("language")
    if not raw_lang:
        raw_lang = data.get("detected_language")
        
    source = "llm"
    confidence = data.get("language_confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = None
            
    if not isinstance(raw_lang, str) or not raw_lang.strip():
        raw_lang = infer_language_from_text(voice_narration)
        source = "fallback"
        confidence = None  # Reset confidence for heuristics detection
        
    # Normalize language name using aliases
    lang = normalize_language(raw_lang)
    
    # Configure lookup and warn on unknown languages
    config = LANGUAGE_CONFIGS.get(lang)
    if not config:
        logger.warning(f"Unknown language detected: {lang}")
        lang = "english"  # Default to English
        config = LANGUAGE_CONFIGS[lang]
        
    # 3. Resolve tasks & clarification status
    tasks_list = []
    gen_tasks = data.get("tasks")
    is_clarification = False
    if isinstance(gen_tasks, list) and len(gen_tasks) == 0:
        is_clarification = True
        
    if isinstance(gen_tasks, list) and gen_tasks:
        for idx, task in enumerate(gen_tasks):
            if not isinstance(task, dict):
                ref_task = default_ref["tasks"][idx % len(default_ref["tasks"])]
                tasks_list.append(copy.deepcopy(ref_task))
                continue
            tasks_list.append({
                "time": str(task.get("time") or "N/A"),
                "title": str(task.get("title") or "Task"),
                "description": str(task.get("description") or "Details not provided."),
                "status": "done"  # Rigidly enforce "done"
            })
    elif is_clarification:
        tasks_list = []
    else:
        tasks_list = copy.deepcopy(default_ref["tasks"])
        
    # 4. Resolve traces (supports both traces dict and agents list formats)
    traces = {}
    gen_traces = data.get("traces")
    if isinstance(gen_traces, dict):
        for k, v in gen_traces.items():
            if isinstance(v, str) and v.strip():
                traces[k] = v.strip()
    
    # Fallback to check if model returned agents list instead of traces dict
    gen_agents = data.get("agents")
    if isinstance(gen_agents, list):
        for a in gen_agents:
            if isinstance(a, dict) and "id" in a and "trace" in a:
                if isinstance(a["trace"], str) and a["trace"].strip():
                    traces[a["id"]] = a["trace"].strip()
                    
    # Build the final 5 agents list
    agents_list = []
    capitalized_lang = lang.capitalize()
    for default_agent in default_ref["agents"]:
        aid = default_agent["id"]
        trace_val = traces.get(aid) or default_agent["trace"]
        working_status = default_agent["workingStatus"]
        done_status = default_agent["doneStatus"]
        
        if aid == "voice-narrator":
            if is_clarification:
                working_status = "Awaiting clarification..."
                done_status = "Awaiting incident telemetry."
            else:
                working_status = "Generating audio briefing..."
                done_status = "Sitrep ready for on-call engineer."
            
        agents_list.append({
            "id": aid,
            "name": default_agent["name"],
            "workingStatus": working_status,
            "doneStatus": done_status,
            "trace": trace_val
        })
        
    # Validation safeguard: verify all voice settings defaults exist, rebuilding from English config if missing
    default_config = LANGUAGE_CONFIGS["english"]
    locale_val = config.get("locale") or default_config["locale"]
    gender_val = config.get("gender") or default_config["gender"]
    style_val = config.get("style") or default_config["style"]
    
    speaking_rate_val = config.get("speaking_rate")
    if speaking_rate_val is None:
        speaking_rate_val = default_config["speaking_rate"]
        
    pitch_val = config.get("pitch")
    if pitch_val is None:
        pitch_val = default_config["pitch"]
        
    # Extract expressive voice settings from configuration
    voice_personality_val = config.get("voice_personality")
    tone_val = config.get("tone")
    energy_val = config.get("energy")
    formality_val = config.get("formality")
        
    # Construct complete voice_settings & detected_language schemas
    voice_settings_dict = {
        "language": lang,
        "locale": locale_val,
        "gender": gender_val,
        "style": style_val,
        "speaking_rate": speaking_rate_val,
        "pitch": pitch_val
    }
    if confidence is not None:
        voice_settings_dict["language_confidence"] = confidence
    if voice_personality_val:
        voice_settings_dict["voice_personality"] = voice_personality_val
    if tone_val:
        voice_settings_dict["tone"] = tone_val
    if energy_val:
        voice_settings_dict["energy"] = energy_val
    if formality_val:
        voice_settings_dict["formality"] = formality_val
        
    detected_language_dict = {
        "language": lang,
        "confidence": confidence,
        "source": source
    }
    
    # Trace log containing all required parameters
    logger.info(
        f"Language Detection Trace - Detected: {raw_lang}, Normalized: {lang}, "
        f"Source: {source}, Confidence: {confidence}, Heuristics Fallback: {'yes' if source == 'fallback' else 'no'}, "
        f"Locale: {locale_val}"
    )
        
    return {
        "agents": agents_list,
        "tasks": tasks_list,
        "voice_narration": voice_narration,
        "voice_settings": voice_settings_dict,
        "detected_language": detected_language_dict
    }

def verbose_validate_and_repair(raw_content: str, attempt_num: int) -> dict:
    """Logs raw output, parses it, records JSON parse and validation durations, and repairs the schema.
    """
    logger.info(f"--- [Attempt {attempt_num}] Validation & Parsing Trace ---")
    logger.info(f"COMPLETE raw Gemini response:\n{raw_content}")
    
    cleaned = clean_json_string(raw_content)
    logger.info(f"Cleaned JSON substring:\n{cleaned}")
    
    # Try parsing JSON
    parse_start = time.perf_counter()
    try:
        data = json.loads(cleaned)
        json_parse_time = (time.perf_counter() - parse_start) * 1000
        logger.info(f"JSON parsing time: {json_parse_time:.2f} ms")
    except Exception as e:
        json_parse_time = (time.perf_counter() - parse_start) * 1000
        logger.error(f"JSON parsing failed after {json_parse_time:.2f} ms!")
        tb_str = "".join(traceback.format_exception(None, e, e.__traceback__))
        logger.error(f"Traceback:\n{tb_str}")
        return None
        
    # Repair and build response
    val_start = time.perf_counter()
    repaired = repair_and_build_response(data)
    val_time = (time.perf_counter() - val_start) * 1000
    logger.info(f"Validation & Repair time: {val_time:.2f} ms")
    
    return repaired

def get_fallback_response(query: str) -> dict:
    """Dynamic configuration-driven fallback system supporting custom query keywords."""
    fallback = copy.deepcopy(DEFAULT_MOCK_RESPONSE)
    lower_query = query.lower()
    
    # Inferred language and config lookup
    detected_lang = infer_language_from_text(query)
    normalized_lang = normalize_language(detected_lang)
    config = LANGUAGE_CONFIGS.get(normalized_lang, LANGUAGE_CONFIGS["english"])
    
    # Assign fallback metadata
    fallback["detected_language"] = {
        "language": normalized_lang,
        "confidence": None,
        "source": "fallback"
    }
    fallback["voice_settings"] = {
        "language": normalized_lang,
        "locale": config["locale"],
        "gender": config["gender"],
        "style": config["style"],
        "speaking_rate": config["speaking_rate"],
        "pitch": config["pitch"]
    }
    
    # Dynamically update the Voice Narrator agent status in the fallback agents list
    for agent in fallback["agents"]:
        if agent["id"] == "voice-narrator":
            agent["workingStatus"] = "Generating audio briefing..."
            agent["doneStatus"] = "Sitrep ready for on-call engineer."
            
    # Truncate user query
    trunc_query = query if len(query) <= 50 else query[:47] + "..."
    
    # Populate localized narration from config
    narr_template = config.get("fallback_narration") or LANGUAGE_CONFIGS["english"]["fallback_narration"]
    fallback["voice_narration"] = narr_template.format(trunc_query=trunc_query)
    
    # Dynamic keyword task updates from config
    fallback_tasks = config.get("fallback_tasks") or LANGUAGE_CONFIGS["english"]["fallback_tasks"]
    
    # Map query keywords to config tasks
    keyword_mapping = {
        "oom": ["oom", "redis", "memory", "eviction", "leak", "ram", "मेमोरी", "कैशे"],
        "deadlock": ["deadlock", "postgres", "database", "lock", "sql", "db", "transaction", "डेटाबेस"],
        "crashloop": ["crashloop", "crash", "pod", "k8s", "kubernetes", "container", "पॉड"],
        "latency": ["latency", "ingress", "nginx", "504", "502", "gateway", "timeout", "slow", "लेटेंसी"],
        "cpu": ["cpu", "scale", "load", "throttling", "spike", "saturation", "hpa", "सीपीयू"],
        "ssl": ["ssl", "tls", "cert", "certificate", "expiry", "expired", "https", "प्रमाणपत्र"]
    }
    
    # Run matching
    matched_key = None
    for key, keywords in keyword_mapping.items():
        if any(k in lower_query for k in keywords):
            matched_key = key
            break
            
    if matched_key and matched_key in fallback_tasks:
        task_data = fallback_tasks[matched_key]
        idx_map = {"oom": 1, "deadlock": 2, "crashloop": 3, "latency": 2, "cpu": 0, "ssl": 1}
        target_idx = idx_map.get(matched_key, 1)
        
        fallback["tasks"][target_idx] = {
            "time": fallback["tasks"][target_idx]["time"],
            "title": task_data["title"],
            "description": task_data["description"],
            "status": "done"
        }
        fallback["voice_narration"] = task_data["narration"].format(trunc_query=trunc_query)
        
    logger.info(
        f"Language Detection Trace (Fallback) - Detected: {detected_lang}, Normalized: {normalized_lang}, "
        f"Source: fallback, Confidence: None, Heuristics Fallback: yes, Locale: {config['locale']}"
    )
        
    return fallback


# ==========================================
# SWARM API ENDPOINTS & HEALTH CHECKS
# ==========================================
@app.get("/")
async def root():
    return {"status": "online", "service": "SeedheOps Swarm Backend", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "SeedheOps Swarm Backend"}

@app.post("/api/swarm", response_model=SwarmResponse)
async def process_swarm_query(request: SwarmRequest):
    req_start = time.perf_counter()
    query = request.query.strip()
    logger.info(f"Incoming query: {query}")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    logger.info("Generation started")
    
    raw_content_1 = ""
    try:
        # First attempt with Gemini 2.5 Flash
        inf_start = time.perf_counter()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        inf_time = (time.perf_counter() - inf_start) * 1000
        logger.info(f"Gemini inference latency: {inf_time:.2f} ms")
        
        raw_content_1 = response.text or ""
        logger.info(f"Total characters received: {len(raw_content_1)}")
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
            completion_tokens = getattr(response.usage_metadata, "candidates_token_count", None)
            total_tokens = getattr(response.usage_metadata, "total_token_count", None)
            if prompt_tokens is not None:
                logger.info(f"Prompt tokens: {prompt_tokens}")
            if completion_tokens is not None:
                logger.info(f"Completion tokens: {completion_tokens}")
            if total_tokens is not None:
                logger.info(f"Total tokens: {total_tokens}")
            
        repaired_json = verbose_validate_and_repair(raw_content_1, attempt_num=1)
        
        if repaired_json:
            total_time = (time.perf_counter() - req_start) * 1000
            logger.info(f"Incoming query: {query}")
            logger.info(f"Detected language: {repaired_json['detected_language']['language']}")
            logger.info(f"Normalized language: {repaired_json['detected_language']['language']}")
            logger.info(f"Locale: {repaired_json['voice_settings']['locale']}")
            logger.info(f"Constructed detected_language object: {repaired_json['detected_language']}")
            logger.info(f"Constructed voice_settings object: {repaired_json['voice_settings']}")
            logger.info(f"Final response JSON immediately before returning from /api/swarm: {json.dumps(repaired_json, ensure_ascii=False)}")
            logger.info("HTTP status code: 200")
            logger.info(f"Generation completed. Total request time: {total_time:.2f} ms")
            return repaired_json
            
        # First attempt failed validation or parsing: execute retry flow
        logger.warning("Retry")
        
        # Determine language detected in the first turn to preserve it in retry
        first_lang = "english"
        try:
            parsed_first = json.loads(clean_json_string(raw_content_1))
            first_lang = parsed_first.get("language") or parsed_first.get("detected_language", {}).get("language")
        except Exception:
            pass
        if not first_lang:
            first_lang = infer_language_from_text(raw_content_1)
        normalized_first = normalize_language(first_lang)
        
        # Build dynamic retry prompt that preserves detected language and tone
        dynamic_retry_prompt = f"Return ONLY valid JSON. The 'voice_narration' MUST be generated entirely and naturally in {normalized_first}. Do NOT translate it or mix languages. Preserve the same narration style and tone."
        
        inf_start_retry = time.perf_counter()
        retry_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[query, dynamic_retry_prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        inf_time_retry = (time.perf_counter() - inf_start_retry) * 1000
        logger.info(f"Gemini inference latency (retry): {inf_time_retry:.2f} ms")
        
        raw_content_2 = retry_response.text or ""
        logger.info(f"Total characters received (retry): {len(raw_content_2)}")
        if hasattr(retry_response, "usage_metadata") and retry_response.usage_metadata:
            prompt_tokens = getattr(retry_response.usage_metadata, "prompt_token_count", None)
            completion_tokens = getattr(retry_response.usage_metadata, "candidates_token_count", None)
            total_tokens = getattr(retry_response.usage_metadata, "total_token_count", None)
            if prompt_tokens is not None:
                logger.info(f"Prompt tokens (retry): {prompt_tokens}")
            if completion_tokens is not None:
                logger.info(f"Completion tokens (retry): {completion_tokens}")
            if total_tokens is not None:
                logger.info(f"Total tokens (retry): {total_tokens}")
            
        repaired_json_retry = verbose_validate_and_repair(raw_content_2, attempt_num=2)
        
        if repaired_json_retry:
            total_time = (time.perf_counter() - req_start) * 1000
            logger.info(f"Incoming query: {query}")
            logger.info(f"Detected language: {repaired_json_retry['detected_language']['language']}")
            logger.info(f"Normalized language: {repaired_json_retry['detected_language']['language']}")
            logger.info(f"Locale: {repaired_json_retry['voice_settings']['locale']}")
            logger.info(f"Constructed detected_language object: {repaired_json_retry['detected_language']}")
            logger.info(f"Constructed voice_settings object: {repaired_json_retry['voice_settings']}")
            logger.info(f"Final response JSON immediately before returning from /api/swarm: {json.dumps(repaired_json_retry, ensure_ascii=False)}")
            logger.info("HTTP status code: 200")
            logger.info(f"Generation completed. Total request time: {total_time:.2f} ms")
            return repaired_json_retry
            
        logger.warning("Fallback used: Both generation attempts failed validation or parsing.")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        logger.warning("Fallback used: Exception raised during Gemini API request execution.")
        
    total_time = (time.perf_counter() - req_start) * 1000
    fallback_res = get_fallback_response(query)
    logger.info(f"Incoming query: {query}")
    logger.info(f"Detected language: {fallback_res['detected_language']['language']}")
    logger.info(f"Normalized language: {fallback_res['detected_language']['language']}")
    logger.info(f"Locale: {fallback_res['voice_settings']['locale']}")
    logger.info(f"Constructed detected_language object: {fallback_res['detected_language']}")
    logger.info(f"Constructed voice_settings object: {fallback_res['voice_settings']}")
    logger.info(f"Final response JSON immediately before returning from /api/swarm: {json.dumps(fallback_res, ensure_ascii=False)}")
    logger.info("HTTP status code: 200")
    logger.info(f"Request completed via fallback. Total request time: {total_time:.2f} ms")
    return fallback_res

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
