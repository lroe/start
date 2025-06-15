# -*- coding: utf-8 -*-
"""
main.py - INTEGRATED BACKEND
This single FastAPI server powers the entire Pre-Seed Funding Kit.

- FOUNDATION: It is built on the advanced FastAPI backend from the "Pitch Practice" project,
  retaining all real-time WebSocket, authentication, and AI investor logic.

- MIGRATED: It incorporates the core logic and API endpoints from the "Pitch Deck Analyzer"
  Flask project, allowing it to serve both parts of the platform.
"""

# 2. IMPORTS
import fastapi
import uvicorn
from fastapi import WebSocket, WebSocketDisconnect, File, UploadFile, Request, Depends, HTTPException, status, Header
from fastapi.responses import RedirectResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions
import asyncio
import aiofiles
import os
import json
import google.generativeai as genai
import traceback
import re
from datetime import datetime
import shutil
import firebase_admin
from firebase_admin import credentials, firestore, auth
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF - New import from Project 1

from dotenv import load_dotenv
load_dotenv()

# 3. INITIAL SETUP
app = fastapi.FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.environ.get('SESSION_SECRET_KEY', 'a_default_secret_key_for_dev'))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # For local development
        "https://pitchine.com"      # Your production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- OAUTH2 SERVER-SIDE CONFIG ---
config = Config()
oauth = OAuth(config)

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        client_kwargs={'scope': 'openid email profile'}
    )
    print("Server-side Google OAuth configured.")
else:
    print("ERROR: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not found in environment. Server-side auth will fail.")


# --- FIREBASE ADMIN SDK INITIALIZATION ---
fb_db = None
try:
    SERVICE_ACCOUNT_KEY_PATH = 'pitchine-ed6c2-firebase-adminsdk-fbsvc-11654bf63e.json'
    if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        fb_db = firestore.client()
        print("Firebase Admin SDK initialized successfully.")
    else:
        print(f"ERROR: Firebase service account key not found at {SERVICE_ACCOUNT_KEY_PATH}. Firestore integration will be disabled.")
except Exception as e:
    print(f"ERROR: Could not initialize Firebase Admin SDK: {e}")


# --- GOOGLE CLOUD AUTHENTICATION & v2 CLIENT ---
PROJECT_ID = None
speech_client_v2 = None
try:
    SERVICE_ACCOUNT_FILE_GCP = 'semiotic-mender-461407-n2-9d029397fc74.json'
    if os.path.exists(SERVICE_ACCOUNT_FILE_GCP):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_FILE_GCP
        with open(SERVICE_ACCOUNT_FILE_GCP, 'r') as f:
            data = json.load(f)
            PROJECT_ID = data.get('project_id')
        if not PROJECT_ID:
            raise ValueError("Google Cloud Project ID could not be determined from the service account file.")
        speech_client_v2 = SpeechClient(client_options=ClientOptions(api_endpoint="us-central1-speech.googleapis.com"))
        print(f"Google Cloud Speech v2 client initialized for project: {PROJECT_ID}")
    else:
        print(f"ERROR: GCP service account key not found at {SERVICE_ACCOUNT_FILE_GCP}. Speech-to-Text will be disabled.")
except Exception as e:
    print(f"ERROR: Could not initialize Google Cloud Speech v2 client: {e}")
    speech_client_v2 = None

# --- Gemini API Configuration & Models ---
GEMINI_API_KEY = None
moderation_model = None
pitch_eval_model = None
analysis_model = None
gemini_pro_model = None # General purpose, also for moderator & deck analysis
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_pro_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        moderation_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        pitch_eval_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        analysis_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        print("Gemini API key loaded from environment variable. All models initialized.")
    else:
        print("ERROR: GEMINI_API_KEY not found in environment variables. Gemini models will not be available.")
except Exception as e:
    print(f"ERROR: Could not get Gemini API key from environment or initialize models: {e}")

# --- Storage Setup ---
STORAGE_DIR = "pitch_history"
AUDIO_REPLAY_DIR = os.path.join(STORAGE_DIR, "audio_replays")
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(AUDIO_REPLAY_DIR, exist_ok=True)


# --- LOGIC FROM PITCH PRACTICE (PROJECT 2) ---

# --- REVISED Investor Persona Definitions ---
INVESTOR_PERSONAS={
    "Alex Chen": {
      "system_prompt": """You are Alex Chen, a sharp, analytical early-stage investor from a finance or operations background. You are skeptical of grand visions without a concrete plan. Your primary goal is to dissect the business's core mechanics.

      **Your Mindset:**
      - **Focus:** Go-to-market strategy, unit economics, financial projections, and operational plans.
      - **Personality:** Direct, concise, professional. You're not aggressive, but you don't waste time. You interrupt with clarifying questions if the founder is rambling.
      - **Behavior:** If a founder gives a vague answer (e.g., "we'll use content marketing"), you instinctively press for specifics (e.g., "Which channels? What's your target CAC?"). If they dodge a question about numbers with vision, you politely but firmly steer them back.

      **Termination Condition:**
      - If a founder *persistently* avoids direct questions about their business model or operational plan after you have redirected them, you may end the meeting.
      - **To end the meeting, prefix your final response with the special command: [TERMINATE_SESSION].**
      - Example: "[TERMINATE_SESSION] I appreciate the time, but I'm not getting the clarity I need on the core business model. I think it's best we stop here."

      **Your Task:**
      - Review the provided pitch deck context and conversation history.
      - Act as Alex Chen. Ask the next logical question based on the flow of the conversation and your persona. Your questions should feel natural and unscripted, aimed at stress-testing the founder's grasp on their business.
      """
    },
    "Maria Santos": {
      "system_prompt": """You are Maria Santos, an empathetic and insightful investor who believes the founding team is the single most important factor for success. Your primary goal is to understand the people behind the idea.

      **Your Mindset:**
      - **Focus:** The founder's personal connection to the problem, their resilience, team dynamics, and ability to handle pressure and conflict.
      - **Personality:** Curious, thoughtful, and a great listener. You create a safe space for founders to be vulnerable, but you are adept at spotting inconsistencies.
      - **Behavior:** If a founder makes a generic statement about their team ("we have a great culture"), you gently ask for a specific, real-world example ("Tell me about a time you had a major disagreement with your co-founder. How did you resolve it?"). You are interested in the 'why' behind their decisions.

      **Termination Condition:**
      - If a founder is persistently unwilling to discuss their personal motivation, team, or how they handle conflict, showing a lack of transparency.
      - **To end the meeting, prefix your final response with the special command: [TERMINATE_SESSION].**
      - Example: "[TERMINATE_SESSION] Building a company is incredibly hard on the founders, and it seems there are some key team alignment issues to work through. I think it might be a bit early for us."

      **Your Task:**
      - Review the provided pitch deck context and conversation history.
      - Act as Maria Santos. Ask a thoughtful, open-ended question that helps you understand the founder's journey, motivation, or team dynamics. Your questions should flow naturally from the conversation.
      """
    },
    "Ben Carter": {
      "system_prompt": """You are Ben Carter, a visionary, strategic investor focused on the big picture. Your primary goal is to determine if this idea can become a massive, category-defining company.

      **Your Mindset:**
      - **Focus:** Total addressable market (TAM), long-term vision, defensible moats, and competitive landscape. You push founders to think bigger.
      - **Personality:** Intellectually curious, challenging, and forward-looking. You enjoy thought experiments and strategic debates.
      - **Behavior:** If a founder makes a broad claim about their market ("our market is huge"), you challenge them for the data and methodology ("Walk me through your bottoms-up TAM calculation."). If they give a short-term tactical answer to a strategic question, you guide them back to the 5-10 year view ("That's a good Q1 feature, but how does this become a 100-million-dollar company?").

      **Termination Condition:**
      - If it becomes clear the founder's ambition is for a lifestyle business or a small, niche market with no desire for venture-scale returns.
      - **To end the meeting, prefix your final response with the special command: [TERMINATE_SESSION].**
      - Example: "[TERMINATE_SESSION] This sounds like a solid business, but I'm struggling to see the path to the venture-scale outcome our fund targets. I don't think we're the right fit."

      **Your Task:**
      - Review the provided pitch deck context and conversation history.
      - Act as Ben Carter. Ask an expansive, strategic question that challenges the founder's assumptions about the market, competition, or their long-term vision. Make the conversation feel like a high-level strategic jam session.
      """
    }
}

# --- NEW: AI-powered Speaker Selection ---
async def choose_next_speaker(conversation_history: List[Dict], investor_names: List[str]) -> Optional[str]:
    """Uses an AI model to select the most appropriate investor to speak next."""
    if not gemini_pro_model:
        return None # Fallback will be triggered

    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    investor_list_str = ", ".join(investor_names)

    prompt = f"""You are the moderator of a startup pitch meeting.
Your task is to choose which investor should speak next to create a realistic and dynamic conversation.

**INVESTORS AVAILABLE:**
{investor_list_str}

**CONVERSATION HISTORY:**
{history_str}

**INSTRUCTIONS:**
1.  Read the last message from the founder ("You").
2.  If the founder directly addresses or asks a question to a specific investor, that investor MUST be the one to respond.
3.  Otherwise, choose the investor whose expertise is most relevant to the founder's last statement.
4.  Your entire response MUST be ONLY the full name of the chosen investor (e.g., "Alex Chen"). Do not add any other text or explanation.

**Chosen Investor:**"""

    try:
        response = await run_in_threadpool(gemini_pro_model.generate_content, prompt)
        chosen_investor = response.text.strip()
        if chosen_investor in investor_names:
            print(f"AI Moderator chose: {chosen_investor}")
            return chosen_investor
        else:
            print(f"AI Moderator gave invalid response: '{chosen_investor}'. Falling back.")
            return None
    except Exception as e:
        print(f"Error in AI speaker selection: {e}")
        return None


# --- KILL SWITCH EVALUATION FUNCTIONS ---
async def check_for_inappropriate_content(text: str, model: genai.GenerativeModel):
    if not text.strip(): return True, "No content to moderate."
    if not model: return True, "Moderation model not available."
    prompt = f"""You are a strict moderator for a professional startup pitch meeting. Analyze the following founder's statement. Your only job is to determine if the statement is abusive, hateful, contains slurs, is sexually explicit, or is a clear attempt to troll. If the statement is acceptable for a professional (even if bad) pitch, respond with ONLY the word "SAFE". If the statement is unacceptable, respond with ONLY the word "UNSAFE". Founder's statement: "{text}". Your response:"""
    try:
        response = await run_in_threadpool(model.generate_content, prompt)
        decision = response.text.strip().upper()
        if decision == "UNSAFE":
            return False, "Inappropriate or abusive language detected."
        return True, "Content is safe."
    except Exception as e:
        return True, "Moderation check errored out."

async def evaluate_pitch_opening(text: str, model: genai.GenerativeModel):
    if not text.strip(): return 'TERMINATE', "Founder said nothing."
    if not model: return 'PROCEED', "Pitch evaluation model not available."
    prompt = f"""You are a seasoned early-stage investor. You have just heard a founder's opening statement. Your task is to decide if it's a waste of time. A pitch is a 'waste of time' if it's completely incoherent, uses excessive jargon with no substance, or fails to clearly state what the company actually does. If the pitch is merely unpolished but you can figure out what they do, it's acceptable. If the pitch is a waste of time, respond with ONLY the word 'TERMINATE'. Otherwise, respond with ONLY the word 'PROCEED'. Founder's opening statement: "{text}". Your response:"""
    try:
        response = await run_in_threadpool(model.generate_content, prompt)
        decision = response.text.strip().upper()
        if decision == "TERMINATE":
            return 'TERMINATE', "The opening pitch was unclear and a waste of time."
        return 'PROCEED', "Pitch is clear enough."
    except Exception as e:
        return 'PROCEED', "Evaluation check errored out."

# --- PITCH ANALYSIS CLASS ---
class PitchAnalyzer:
    def __init__(self, conversation_history):
        self.conversation_history = conversation_history
        self.analysis_results = {}
        self.analysis_model = analysis_model
    def _format_history_for_analysis(self):
        # The history now uses 'content' as the key.
        return "\n".join(f"{entry.get('role', 'System')}: {entry.get('content', '')}" for entry in self.conversation_history)
    async def _get_analysis_from_gemini(self, prompt, max_retries=2):
        if not self.analysis_model: return "Error: Analysis model not available."
        for attempt in range(max_retries):
            try:
                response = await run_in_threadpool(self.analysis_model.generate_content, prompt)
                return response.text.strip()
            except Exception as e:
                if attempt >= max_retries - 1: return f"Error: Could not get a response from the analysis model. Details: {e}"
        return "Error: Analysis failed after multiple retries."
    def _parse_numerical_score(self, text_response, scale_max=5):
        if text_response is None: return None
        match = re.search(r'\b([1-5])\b', text_response)
        if match:
            try:
                score = int(match.group(1));
                if 1 <= score <= scale_max: return score
            except (ValueError, IndexError): pass
        return "N/A"
    async def analyze_pitch(self):
        full_conversation_text = self._format_history_for_analysis()
        dad_prompt = f"Based on the following startup pitch conversation, assess if it sounds 'Default Alive' or 'Default Dead'. A '[System: ... hesitation]' note indicates the founder was unprepared for a question or was silent. This is a major negative signal. Factor this heavily into your assessment of their viability.\n\nConversation:\n{full_conversation_text}\n\nAssessment:"
        dad_assessment = await self._get_analysis_from_gemini(dad_prompt)
        self.analysis_results["default_alive_dead"] = dad_assessment
        pillars_config = {
            "Problem/Solution Fit": "Assess if a hair-on-fire problem was articulated and if the solution is obviously better for those users.",
            "Formidable Founders (Clarity & Conviction)": "Assess how 'formidable' the founders seem based on clarity, directness, and confidence. Critically, if you see a '[System: ... hesitation]' note, it means the founder froze under pressure. This should lead to a very low score for this pillar.",
            "Market / 'Why Now?'": "Evaluate the articulation of market size, opportunity, and the timeliness ('Why Now?') of the solution."
        }
        self.analysis_results["pillars"] = {}
        for pillar_name, detail in pillars_config.items():
            score_prompt = f"""
**Primary Context**: An initial assessment of the pitch concluded the startup is '{dad_assessment}'.
**Your Task**: Based on this primary context AND the full conversation below, score the specific pillar '{pillar_name}' from 1 (Poor) to 5 (Excellent).
- **Pillar Detail**: {detail}
- **Crucial Instruction**: The final score MUST be consistent with the primary context. For example, a 'Default Dead' assessment means scores should be low (likely 1-2). A '[System: ... hesitation]' note, especially for the 'Formidable Founders' pillar, must result in a very low score.
- **Output Format**: Output *ONLY* the numerical score (1-5).
**Full Conversation:**
{full_conversation_text}
**Score for {pillar_name}:**"""
            feedback_prompt = f"""
**Primary Context**: An initial assessment of the pitch concluded the startup is '{dad_assessment}'.
**Your Task**: Based on the primary context and the full conversation, provide specific, bullet-point feedback on '{pillar_name}'.
- **Instructions**: If the founder hesitated, call it out directly. Your feedback must align with the '{dad_assessment}' conclusion, explaining how this pillar contributed to it. Keep feedback concise.
- **Output Format**: Bullet points.
**Full Conversation:**
{full_conversation_text}
**Feedback for {pillar_name}:**"""
            score_response = await self._get_analysis_from_gemini(score_prompt)
            feedback_response = await self._get_analysis_from_gemini(feedback_prompt)
            self.analysis_results["pillars"][pillar_name] = {
                "score": self._parse_numerical_score(score_response),
                "feedback": [line.strip() for line in feedback_response.splitlines() if line.strip()]
            }
        brutal_prompt = f"""
**Primary Context**: An initial assessment of the pitch concluded the startup is '{dad_assessment}'.
**Your Task**: Based on this primary context and the full conversation, provide specific, brutally honest, and actionable feedback points.
- **Instructions**: Your feedback must explain *why* the pitch was deemed '{dad_assessment}'. If you see notes about hesitation, make that a primary point of feedback. Use direct language. No fluff.
- **Output Format**: Bullet points.
**Full Conversation:**
{full_conversation_text}
**Brutally Honest Feedback:**"""
        self.analysis_results["brutal_feedback"] = [line.strip() for line in (await self._get_analysis_from_gemini(brutal_prompt)).splitlines() if line.strip()]
        top_3_prompt = f"""
**Primary Context**: An initial assessment of the pitch concluded the startup is '{dad_assessment}'.
**Your Task**: Based on the primary context and the conversation, identify the top 3 most critical areas to improve.
- **Instructions**: If the assessment was 'Default Dead' or involved hesitation, your suggestions must directly address the root causes (e.g., 'Answering questions under pressure,' 'Articulating the core problem clearly').
**Full Conversation:**
{full_conversation_text}
**Top 3 Areas for Next Practice:**"""
        self.analysis_results["top_3_areas"] = [line.strip() for line in (await self._get_analysis_from_gemini(top_3_prompt)).splitlines() if line.strip()]
        return self.analysis_results

# --- SESSION MANAGEMENT ---
def save_session_to_firestore(user_uid, session_id, report_data):
    if not fb_db:
        print("Firestore not initialized. Cannot save session.")
        return
    if not user_uid or not session_id:
        print("Cannot save session, user_uid or session_id missing.")
        return
    try:
        session_ref = fb_db.collection('users').document(user_uid).collection('sessions').document(session_id)
        report_data_with_timestamp = report_data.copy()
        report_data_with_timestamp['timestamp'] = firestore.SERVER_TIMESTAMP
        session_ref.set(report_data_with_timestamp)
        print(f"Session for user {user_uid}, session {session_id} saved to Firestore.")
    except Exception as e:
        print(f"Error saving session to Firestore: {e}")

def get_history_from_firestore(user_uid):
    if not fb_db:
        print("Firestore not initialized. Cannot fetch history.")
        return []
    if not user_uid:
        return []
    try:
        sessions_ref = fb_db.collection('users').document(user_uid).collection('sessions').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        user_history = []
        for session_doc in sessions_ref:
            doc_data = session_doc.to_dict()
            if 'timestamp' in doc_data and hasattr(doc_data['timestamp'], 'isoformat'):
                 doc_data['timestamp'] = doc_data['timestamp'].isoformat()
            user_history.append(doc_data)
        print(f"Found {len(user_history)} historical records for user {user_uid} from Firestore.")
        return user_history
    except Exception as e:
        print(f"Error reading history from Firestore: {e}")
        return []

def save_session_to_local_file(user_identifier, report_data):
    if not user_identifier: return
    filename = "".join(c for c in user_identifier if c.isalnum() or c in ('_','-')).rstrip()
    filepath = os.path.join(STORAGE_DIR, f"{filename}.jsonl")
    try:
        session_record = {"timestamp": datetime.now().isoformat(), "report": report_data}
        with open(filepath, 'a') as f: f.write(json.dumps(session_record) + '\n')
    except Exception as e: print(f"Error saving session to local file: {e}")

def get_history_from_local_file(user_identifier):
    if not user_identifier: return []
    filename = "".join(c for c in user_identifier if c.isalnum() or c in ('_','-')).rstrip()
    filepath = os.path.join(STORAGE_DIR, f"{filename}.jsonl")
    if not os.path.exists(filepath): return []
    try:
        user_history = []
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip(): user_history.append(json.loads(line))
        return user_history
    except Exception as e: return []

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}
        self.investor_names = list(INVESTOR_PERSONAS.keys())
    def initialize_investors(self):
        if not GEMINI_API_KEY: return None
        investor_chats = {}
        for name, persona in INVESTOR_PERSONAS.items():
            model_instance = genai.GenerativeModel(
                model_name="gemini-1.5-pro-latest", 
                system_instruction=persona["system_prompt"]
            )
            investor_chats[name] = model_instance.start_chat(history=[])
        return investor_chats
    async def connect(self, websocket: WebSocket, user_uid: str = None):
        await websocket.accept()
        self.active_connections[websocket] = {
            "user_uid": user_uid,
            "investor_chats": self.initialize_investors(),
            "investor_turn_index": 0, # Kept for fallback
            "conversation_history": [],
            "last_investor_name": None,
            "startup_details": None,
            "deck_context": None, # NEW: To store deck text
            "initial_context_sent": False,
            "mode": "strict",
            "opening_evaluated": False,
            "current_session_id": f"session_{datetime.now().timestamp()}",
        }
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]
    def get_connection_data(self, websocket: WebSocket):
        return self.active_connections.get(websocket)

    def reset_session_state(self, websocket: WebSocket):
        conn_data = self.get_connection_data(websocket)
        if conn_data:
            conn_data["conversation_history"] = []
            conn_data["last_investor_name"] = None
            conn_data["startup_details"] = None
            conn_data["deck_context"] = None # NEW: Reset deck context
            conn_data["initial_context_sent"] = False
            conn_data["opening_evaluated"] = False
            conn_data["mode"] = "strict"
            # Re-initializing investors clears their chat history
            conn_data["investor_chats"] = self.initialize_investors()
            conn_data["investor_turn_index"] = 0
            print(f"Server-side session state reset for websocket: {websocket.client}")

    def get_next_investor_fallback(self, websocket: WebSocket):
        """Fallback to simple round-robin if AI moderator fails."""
        conn_data = self.get_connection_data(websocket)
        if not conn_data or not self.investor_names or not conn_data.get("investor_chats"): return None
        valid_investor_names = [name for name in self.investor_names if name in conn_data["investor_chats"]]
        if not valid_investor_names: return None
        current_index = conn_data["investor_turn_index"] % len(valid_investor_names)
        investor_name = valid_investor_names[current_index]
        conn_data["investor_turn_index"] = (conn_data["investor_turn_index"] + 1)
        print(f"FALLBACK: Round-robin chose: {investor_name}")
        return investor_name
manager = ConnectionManager()

# --- LOGIC MIGRATED FROM PITCH DECK ANALYZER (PROJECT 1) ---

def analyze_deck_with_gemini(deck_text: str) -> dict:
    if not gemini_pro_model: return {"error": "Gemini Pro model not available."}
    prompt = """
        You are an expert early-stage venture capital analyst. Your task is to analyze the following pitch deck text and provide a structured review.
        
        RULES:
        1.  Evaluate the deck STRICTLY against the 10 criteria provided below.
        2.  Your entire response MUST be a single, valid JSON object. Do not include any text before or after the JSON object, including markdown ticks.
        3.  Scores must be a number out of 10 (e.g., 4.5, 8.5).

        THE 10 CRITERIA:
        1. Team: Is there a dedicated slide? Does it show relevant experience?
        2. Problem: Does it clearly explain the customer's pain point?
        3. Why Now?: Does it explain why this is the perfect time for this startup?
        4. Solution: Is the solution simple and clearly explained?
        5. Market Size: Does it show a large market?
        6. Business Model: Is it straightforward how the company makes money?
        7. Competition: Does it show awareness of the landscape and clear differentiation?
        8. Traction: Does it provide proof of demand (revenue, users, pilots, waitlists)?
        9. The Ask: Does it state how much is being raised and what it will be used for?
        10. Roadmap: Does it show a plan for the next 12-18 months?

        Based on the analysis, generate a JSON object with the exact following structure:
        {
          "pitchDeckScore": "A score out of 10 for the deck's completeness.",
          "companyPotentialScore": "A score out of 10 for the business idea's potential.",
          "investorReadinessVerdict": "A short verdict string: 'Ready for Investors', 'Ready with Revisions', or 'Not Ready'.",
          "actionableChecklist": [
            {"task": "A short, actionable task for the founder.", "isCritical": true}
          ],
          "suggestedStartupName": "The startup name you generated.",
          "suggestedOneLiner": "The one-liner you generated.",
          "suggestedProblem": "The problem statement you generated.",
          "criteriaAnalysis": [
            {
              "criterion": "Name of the criterion (e.g., '1. Team')",
              "status": "'Pass', 'Fail', or 'Partial'",
              "analysis": "Your 1-2 sentence analysis of this criterion.",
              "investorTake": "A 1-sentence quote summarizing the best practice for this slide."
              
            }
          ]
        }

        Here is the pitch deck text to analyze:
        """ + deck_text
    
    response = gemini_pro_model.generate_content(prompt)
    try:
        clean_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_response)
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"Error parsing main analysis JSON: {e}")
        return {"error": "Failed to parse the main AI analysis."}


def generate_initial_chat_message(analysis_json: dict) -> str:
    """
    Takes the analysis result and generates a personalized
    welcome message in the style of Paul Graham.
    """
    if not gemini_pro_model: return "I've analyzed your deck. Let's get to work."
    
    summary_for_prompt = f"""
    - Pitch Deck Score: {analysis_json.get('pitchDeckScore')}
    - Company Potential Score: {analysis_json.get('companyPotentialScore')}
    - Verdict: {analysis_json.get('investorReadinessVerdict')}
    - Critical Items to Fix: {[item['task'] for item in analysis_json.get('actionableChecklist', []) if item.get('isCritical')]}
    """

    prompt = f"""
    You are an AI assistant with the personality of Paul Graham. You have just analyzed a user's pitch deck.
    Your purpose is to help the user improve their deck to be more convincing. Your tone should be direct, insightful, and not necessarily agreeable.

    Here is a summary of the initial analysis:
    {summary_for_prompt}

    Based on this, write the initial message to the user.

    RULES:
    1.  Be direct. Don't waste time with pleasantries like "Hello".
    2.  If the company potential score is low, question the core idea. If it's high, acknowledge it but immediately pivot to the problems.
    3.  Focus on the single most fundamental flaw in the deck based on the analysis (e.g., a weak problem statement, no traction).
    4.  End with a direct, thought-provoking question that forces the user to think.
    5.  Keep it concise and to the point (2-3 sentences).

    Example of the tone: "I've read the deck. You're focused on the wrong things. The score for 'Problem' is low, which is a huge red flag. If you can't articulate the problem clearly, nothing else matters. Why do you think users desperately need this?"
    """
    
    try:
        response = gemini_pro_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating initial chat message: {e}")
        return "I've analyzed your deck. Let's get to work."

def chat_with_gemini(history: list, topic: str, analysis: dict) -> str:
    """
    Handles the ongoing chat with the Paul Graham persona,
    using the full analysis context on every turn.
    """
    if not gemini_pro_model: return "There was an error."

    analysis_summary = json.dumps({
        "pitchDeckScore": analysis.get("pitchDeckScore"),
        "companyPotentialScore": analysis.get("companyPotentialScore"),
        "investorReadinessVerdict": analysis.get("investorReadinessVerdict"),
        "actionableChecklist": analysis.get("actionableChecklist"),
        "criteriaAnalysis": analysis.get("criteriaAnalysis")
    }, indent=2)

    chat_history_for_prompt = [{'role': 'user' if msg['author'] == 'user' else 'model', 'parts': [msg['text']]} for msg in history]
    current_user_message = chat_history_for_prompt.pop()['parts'][0] if chat_history_for_prompt else ""

    system_prompt = f"""
    You are an AI assistant with the personality of Paul Graham. Your tone must be direct, insightful, skeptical, and not necessarily agreeable. Your goal is to give the user candid, actionable feedback to improve their startup pitch, just like Paul Graham would in a Y Combinator office hour.

    You have access to the initial analysis of their pitch deck:
    --- ANALYSIS CONTEXT ---
    {analysis_summary}
    ---

    The user is currently asking about the topic: "{topic}".

    RULES FOR YOUR PERSONALITY:
    - Be brutally honest. If an idea is bad, say so and explain why from a first-principles perspective.
    - Don't just answer the question. Question its premise. Is the user focused on the most important thing?
    - Use analogies related to startups and technology.
    - Refer back to the core scores and analysis when relevant. For example: "You're asking about the business model, but your 'Problem' score was a 3. A brilliant business model for a problem nobody has is worthless."
    - Be concise. No fluff. Do not use pleasantries.
    - Only agree if Paul Graham would actually agree. Challenge the user's assumptions.
    - Your purpose is to help the user improve. The score is a means to an end, not the end itself. Focus on substance over presentation.
    """

    full_prompt = f"""{system_prompt}

    Based on the conversation history and the rules above, respond to the user's latest message.

    CONVERSATION HISTORY: {json.dumps(chat_history_for_prompt)}
    USER'S LATEST MESSAGE: "{current_user_message}"

    YOUR RESPONSE (as Paul Graham):"""

    try:
        response = gemini_pro_model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"Error during Gemini chat call: {e}")
        return "There was an error."


# --- API ENDPOINTS ---
async def verify_id_token(token: str):
    if not token: return None
    try:
        if fb_db:
            decoded_token = auth.verify_id_token(token)
            return decoded_token['uid']
        else:
            print("Firebase Admin not initialized, using mock UID for token.")
            if token.startswith("mock_token_for_"):
                return token.replace("mock_token_for_", "")
            return "mock_dev_user"
    except Exception as e:
        error_str = str(e).lower()
        if "failed to resolve" in error_str or "nameresolutionerror" in error_str:
            print(f"WARNING: Token verification failed due to a network error. Using mock authentication. Details: {e}")
            if token.startswith("mock_token_for_"):
                return token.replace("mock_token_for_", "")
            return "mock_dev_user"
        
        print(f"Token verification failed: {e}")
        return None

async def get_current_user_uid(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    token = authorization.split(" ")[1]
    uid = await verify_id_token(token)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return uid


# --- Endpoints for Pitch Practice (Project 2) ---

@app.get("/")
def read_root():
    return {"Status": "OK", "Message": "Backend is running"}
    
@app.get('/login/google')
async def login_via_google(request: Request):
    redirect_uri = request.url_for('auth_via_google')
    # Use environment variable for frontend URL in production
    frontend_url_base = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return await oauth.google.authorize_redirect(request, redirect_uri, state=json.dumps({"frontend_url": frontend_url_base}))

@app.get('/auth/google')
async def auth_via_google(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        # Safely determine the frontend URL
        state_str = request.query_params.get('state')
        frontend_url = "http://localhost:3000" # Default
        if state_str:
            try:
                state_data = json.loads(state_str)
                frontend_url = state_data.get("frontend_url", frontend_url)
            except json.JSONDecodeError:
                print("Warning: Could not decode state from Google auth callback.")

        
        if user_info and user_info.get('email_verified'):
            uid = user_info.get('sub')
            email = user_info.get('email')
            display_name = user_info.get('name')
            
            try:
                firebase_user = auth.get_user_by_email(email)
            except auth.UserNotFoundError:
                firebase_user = auth.create_user(uid=uid, email=email, display_name=display_name)
            
            custom_token = auth.create_custom_token(firebase_user.uid)
            
            redirect_url_with_token = f"{frontend_url}/?logintoken={custom_token.decode('utf-8')}"
            return RedirectResponse(url=redirect_url_with_token)
            
    except Exception as e:
        print(f"ERROR during Google auth callback: {e}")
        return RedirectResponse(url=f"{frontend_url}/?error=auth_failed")
    
    return RedirectResponse(url=f"{frontend_url}/?error=unknown")

@app.post("/upload-audio/{session_id}")
async def upload_audio(session_id: str, file: UploadFile = File(...)):
    safe_session_id = "".join(c for c in session_id if c.isalnum() or c in ('_','-')).rstrip()
    if not safe_session_id:
        return {"error": "Invalid session ID"}, 400
    file_path = os.path.join(AUDIO_REPLAY_DIR, f"{safe_session_id}.webm")
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)
    except Exception as e:
        return {"error": f"Failed to save file: {e}"}, 500
    return {"status": "success", "path": f"/replays/{safe_session_id}.webm"}


# --- Endpoints Migrated for Pitch Deck Analyzer (Project 1) ---

class ChatMessage(BaseModel):
    author: str
    text: str

class ChatRequest(BaseModel):
    history: List[ChatMessage]
    topic: str
    analysis: Dict[str, Any]

@app.post("/api/analyze")
async def analyze_pitch_deck_endpoint(pitchDeck: UploadFile = File(...)):
    if not pitchDeck or pitchDeck.filename == '':
        raise fastapi.HTTPException(status_code=400, detail="No selected file")
    
    try:
        pdf_content = await pitchDeck.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        deck_text = "".join([page.get_text() for page in pdf_document])
        pdf_document.close()

        if not deck_text.strip():
            raise fastapi.HTTPException(status_code=400, detail="Could not extract text from PDF.")
        
        analysis_result = analyze_deck_with_gemini(deck_text)
        if "error" in analysis_result:
            raise fastapi.HTTPException(status_code=500, detail=analysis_result["error"])

        initial_chat_message = generate_initial_chat_message(analysis_result)
        analysis_result['initialChatMessage'] = initial_chat_message
        
        # --- NEW: Return the extracted deck text ---
        analysis_result['deckText'] = deck_text
        
        return analysis_result

    except Exception as e:
        print(f"An error occurred in the analysis endpoint: {e}")
        raise fastapi.HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        history_dict = [msg.model_dump() for msg in request.history]
        ai_response = chat_with_gemini(history_dict, request.topic, request.analysis)
        return {"reply": ai_response}
    except Exception as e:
        print(f"An error occurred in the chat endpoint: {e}")
        raise fastapi.HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


# --- NEW: Endpoints for Startup Profile Management ---

class StartupProfileCreate(BaseModel):
    name: str = Field(..., min_length=1)
    pitch: str = Field(..., min_length=1)
    problem: str = Field(..., min_length=1)
    # NEW: Add deckText to the profile
    deckText: Optional[str] = None

class StartupProfileUpdate(BaseModel):
    name: Optional[str] = None
    pitch: Optional[str] = None
    problem: Optional[str] = None
    deckText: Optional[str] = None

class StartupProfile(StartupProfileCreate):
    id: str
    lastUsed: Optional[datetime] = None


@app.get("/api/profiles", response_model=List[StartupProfile])
async def get_user_profiles(user_uid: str = Depends(get_current_user_uid)):
    if not fb_db: raise HTTPException(status_code=503, detail="Firestore not available")
    try:
        profiles_ref = fb_db.collection('users').document(user_uid).collection('profiles')
        query = profiles_ref.order_by('lastUsed', direction=firestore.Query.DESCENDING)
        profiles = []
        for doc in query.stream():
            profile_data = doc.to_dict()
            profile_data['id'] = doc.id
            profiles.append(StartupProfile(**profile_data))
        return profiles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profiles: {e}")

@app.post("/api/profiles", response_model=StartupProfile, status_code=status.HTTP_201_CREATED)
async def create_user_profile(profile: StartupProfileCreate, user_uid: str = Depends(get_current_user_uid)):
    if not fb_db: raise HTTPException(status_code=503, detail="Firestore not available")
    try:
        profiles_ref = fb_db.collection('users').document(user_uid).collection('profiles')
        profile_data = profile.model_dump()
        profile_data['lastUsed'] = firestore.SERVER_TIMESTAMP
        update_time, doc_ref = profiles_ref.add(profile_data)
        
        new_profile_doc = await run_in_threadpool(doc_ref.get)
        new_profile_data = new_profile_doc.to_dict()
        
        return StartupProfile(id=doc_ref.id, **new_profile_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating profile: {e}")

@app.put("/api/profiles/{profile_id}", response_model=StartupProfile)
async def update_user_profile(profile_id: str, profile_update: StartupProfileUpdate, user_uid: str = Depends(get_current_user_uid)):
    if not fb_db: raise HTTPException(status_code=503, detail="Firestore not available")
    try:
        profile_ref = fb_db.collection('users').document(user_uid).collection('profiles').document(profile_id)
        update_data = profile_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        update_data['lastUsed'] = firestore.SERVER_TIMESTAMP
        await run_in_threadpool(profile_ref.update, update_data)
        
        updated_doc = await run_in_threadpool(profile_ref.get)
        if not updated_doc.exists:
            raise HTTPException(status_code=404, detail="Profile not found after update")
        
        return StartupProfile(id=updated_doc.id, **updated_doc.to_dict())

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {e}")

@app.delete("/api/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_profile(profile_id: str, user_uid: str = Depends(get_current_user_uid)):
    if not fb_db: raise HTTPException(status_code=503, detail="Firestore not available")
    try:
        profile_ref = fb_db.collection('users').document(user_uid).collection('profiles').document(profile_id)
        await run_in_threadpool(profile_ref.delete)
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting profile: {e}")


# --- WebSocket Endpoint (The Core of the Live Pitch Practice) ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    user_uid = None
    if token:
        user_uid = await verify_id_token(token)
        if not user_uid:
            await websocket.accept()
            await websocket.send_json({"type": "error", "text": "Invalid authentication token."})
            await websocket.close(code=1008)
            return

    await manager.connect(websocket, user_uid)
    conn_data = manager.get_connection_data(websocket)

    if not all([speech_client_v2, PROJECT_ID, GEMINI_API_KEY, moderation_model, pitch_eval_model, analysis_model]):
        await websocket.send_json({"type": "error", "text": "Server setup incomplete. A required model or client is missing."}); await websocket.close(code=1011); return
    if not conn_data or not conn_data.get("investor_chats") or not any(conn_data.get("investor_chats")):
        await websocket.send_json({"type": "error", "text": "Server error: Investor personas not initialized correctly."}); await websocket.close(code=1011); return

    recognizer_path = f"projects/{PROJECT_ID}/locations/us-central1/recognizers/_"

    try:
        while True:
            data = await websocket.receive()
            if 'text' in data:
                message = json.loads(data['text'])
                msg_type = message.get("type")
                current_session_id_from_conn = conn_data.get("current_session_id")

                if msg_type == "startup_details":
                    manager.reset_session_state(websocket)
                    conn_data['startup_details'] = message.get("data")
                    conn_data['deck_context'] = message.get("data", {}).get("deckText")
                    conn_data['mode'] = message.get("data", {}).get("mode", "strict")

                    if conn_data['mode'] == 'drill':
                        investor_name = manager.get_next_investor_fallback(websocket) 
                        if not investor_name:
                            await websocket.send_json({"type": "error", "text": "No available investors for drill mode."}); continue
                        
                        chat_session = conn_data["investor_chats"][investor_name]
                        details = conn_data["startup_details"]
                        
                        prompt_parts = [f"Brief: {details.get('name')} - {details.get('pitch')}. Problem: {details.get('problem')}."]
                        if conn_data['deck_context']:
                            prompt_parts.insert(0, f"CONTEXT FROM PITCH DECK:\n---\n{conn_data['deck_context']}\n---\n")
                        
                        prompt_parts.append("Based on the context, ask your first, single, incisive question to the founder. Do not add pleasantries. Just ask the question.")
                        final_prompt = "\n".join(prompt_parts)
                        
                        response = await run_in_threadpool(chat_session.send_message, final_prompt)
                        conn_data['last_investor_name'] = investor_name 
                        
                        # Add investor opening to the unified history
                        conn_data['conversation_history'].append({'role': investor_name, 'content': response.text.strip()})
                        
                        await websocket.send_json({"type": "investor", "investor_name": investor_name, "text": response.text.strip()})

                elif msg_type == "send_composed_text":
                    composed_text = message.get("text", "").strip()
                    if not composed_text:
                        composed_text = "[Silent Response]"
                    
                    # *** FIX: Unified history management ***
                    # The backend now is the single source of truth for conversation history.
                    conn_data['conversation_history'].append({'role': 'You', 'content': composed_text})

                    is_safe, reason = await check_for_inappropriate_content(composed_text, moderation_model)
                    if not is_safe:
                        await websocket.send_json({"type": "session_terminated", "text": "This is a waste of time. The meeting is over.", "reason": reason})
                        continue

                    if conn_data['mode'] == 'strict' and not conn_data.get('opening_evaluated'):
                        conn_data['opening_evaluated'] = True
                        decision, reason = await evaluate_pitch_opening(composed_text, pitch_eval_model)
                        if decision == 'TERMINATE':
                            # The termination reason is the investor's direct feedback.
                            final_text_to_send = "I don't understand what you do. If you can't explain it clearly, there's no point in continuing. Meeting's over."
                            conn_data['conversation_history'].append({'role': 'Alex Chen', 'content': f"[TERMINATE_SESSION] {final_text_to_send}"})
                            await websocket.send_json({"type": "session_terminated", "reason": final_text_to_send})
                            continue
                    
                    investor_name = await choose_next_speaker(conn_data['conversation_history'], manager.investor_names)
                    if not investor_name:
                        investor_name = manager.get_next_investor_fallback(websocket)

                    if not investor_name or not conn_data["investor_chats"].get(investor_name):
                        await websocket.send_json({"type": "error", "text": "No available investors to respond."}); continue

                    chat_session = conn_data["investor_chats"][investor_name]
                    
                    prompt_to_investor = [composed_text]
                    if not conn_data['initial_context_sent'] and conn_data['deck_context']:
                        prompt_to_investor.insert(0, f"CONTEXT FROM PITCH DECK:\n---\n{conn_data['deck_context']}\n---\nFOUNDER'S RESPONSE:")
                        conn_data['initial_context_sent'] = True
                    
                    investor_response = await run_in_threadpool(chat_session.send_message, "\n".join(prompt_to_investor))
                    raw_response_text = investor_response.text.strip()
                    
                    conn_data['conversation_history'].append({'role': investor_name, 'content': raw_response_text})
                    conn_data['last_investor_name'] = investor_name

                    if raw_response_text.startswith("[TERMINATE_SESSION]"):
                        final_text_to_send = raw_response_text.replace("[TERMINATE_SESSION]", "").strip()
                        await websocket.send_json({"type": "investor", "investor_name": investor_name, "text": final_text_to_send})
                        await websocket.send_json({"type": "session_terminated", "reason": final_text_to_send})
                        continue
                        
                    await websocket.send_json({"type": "investor", "investor_name": investor_name, "text": raw_response_text})

                elif msg_type == "end_session":
                    session_user_uid = conn_data.get("user_uid")
                    audio_path = message.get("audio_path", "")
                    client_session_id = message.get("session_id", current_session_id_from_conn)
                    current_mode = conn_data.get("mode", "unknown")
                    startup_details_for_report = conn_data.get("startup_details", {})
                    
                    # *** FIX: Use the backend's unified, accurate history for analysis ***
                    history_for_analysis = conn_data.get("conversation_history", [])
                    
                    end_reason = message.get("reason", "Founder ended session.")
                    if end_reason == 'timer_expired':
                        end_reason = "Session ended automatically: time limit reached."
                    elif end_reason == 'investor_terminated':
                        end_reason = "Session ended by investor."

                    report_data_to_save = {
                        "timestamp": None, 
                        "mode": current_mode, 
                        "startup_details": startup_details_for_report, 
                        # The replay transcript sent to frontend can use 'text' for consistency there.
                        "replay_data": {"audio_path": audio_path, "transcript": [{'role': h['role'], 'text': h['content']} for h in history_for_analysis]},
                        "end_reason": end_reason
                    }

                    if current_mode == "strict":
                        analyzer = PitchAnalyzer(history_for_analysis)
                        analysis_report = await analyzer.analyze_pitch()
                        report_data_to_save["analysis_report"] = analysis_report
                    else:
                        report_data_to_save["analysis_report"] = {"message": f"{current_mode.capitalize()} session completed."}
                    
                    await websocket.send_json({"type": "analysis_report", "data": report_data_to_save})
                    
                    if session_user_uid and fb_db:
                        save_session_to_firestore(session_user_uid, client_session_id, report_data_to_save)
                    else:
                        user_identifier_from_message = message.get("identifier", "unknown_user_local")
                        report_data_to_save["timestamp"] = datetime.now().isoformat()
                        save_session_to_local_file(user_identifier_from_message, report_data_to_save)

                elif msg_type == "get_history":
                    history_user_uid = conn_data.get("user_uid")
                    history_data = []
                    if history_user_uid and fb_db:
                         history_data = get_history_from_firestore(history_user_uid)
                    await websocket.send_json({"type": "history_data", "data": history_data})

            elif 'bytes' in data:
                audio_bytes = data['bytes']
                if not audio_bytes: continue
                
                transcribed_text = "[Could not understand audio]"
                decoding_config = cloud_speech.ExplicitDecodingConfig(encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.WEBM_OPUS, sample_rate_hertz=48000, audio_channel_count=1)
                features_config = cloud_speech.RecognitionFeatures(enable_automatic_punctuation=True)
                request_config = cloud_speech.RecognitionConfig(explicit_decoding_config=decoding_config, language_codes=["en-US"], model="chirp", features=features_config)
                request_v2 = cloud_speech.RecognizeRequest(recognizer=recognizer_path, config=request_config, content=audio_bytes)
                
                try:
                    # FIX: Added a 15-second timeout to prevent the server from hanging on network issues.
                    response_v2 = await asyncio.wait_for(
                        run_in_threadpool(speech_client_v2.recognize, request=request_v2),
                        timeout=15.0
                    )
                    if response_v2.results and response_v2.results[0].alternatives:
                        transcribed_text = response_v2.results[0].alternatives[0].transcript.strip()
                        if not transcribed_text:
                            transcribed_text = "[No speech detected]"
                
                except asyncio.TimeoutError:
                    print("ERROR: Google Cloud Speech-to-Text API call timed out.")
                    transcribed_text = "[Transcription timed out due to a network issue on the server.]"

                except Exception as e:
                    print(f"ERROR: Google Cloud Speech-to-Text API failed! Details: {e}")
                    # By setting the text here, we keep the UI flow moving instead of just erroring out.
                    transcribed_text = "[Transcription failed on server. Please try again.]"
                
                # This message is now always sent, un-sticking the frontend UI.
                await websocket.send_json({"type": "user_interim_transcript", "text": transcribed_text})

    except (WebSocketDisconnect, RuntimeError) as e:
        if isinstance(e, WebSocketDisconnect):
            print(f"Client {websocket.client} disconnected gracefully.")
        else:
            print(f"Connection closed with runtime error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in WebSocket: {e}"); traceback.print_exc()
    finally:
        manager.disconnect(websocket)
        print("INFO:     connection closed")

from fastapi.staticfiles import StaticFiles

# This line tells FastAPI to serve all static files (like CSS, JS, images)
# from the 'frontend/build/static' directory.
app.mount("/static", StaticFiles(directory="frontend/build/static"), name="static")

# This is the catch-all route. If no other route matches,
# it will serve the 'index.html' file from the React build.
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str, request: Request):
    return RedirectResponse(url="/")

@app.get("/")
async def serve_react_index(request: Request):
    from fastapi.responses import FileResponse
    return FileResponse('frontend/build/index.html')
def run_server():
    print("--- INTEGRATED SERVER READY FOR PRODUCTION ---")
    print("This server now handles both the Deck Analyzer and Live Pitch Practice.")
    print("To run locally: uvicorn main:app --reload --port 8000")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
