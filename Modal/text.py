"""
text.py - Question-Answer Batch Evaluation Module
==================================================
LangChain + LangGraph implementation with batch evaluation.

Key Innovation: No answer extraction!
- Extract questions (simple)
- Extract full text + all word bboxes
- LLM evaluates all questions in one call
- Enrich feedback with bboxes

Flow:
1. Extract questions
2. Extract full text (no segmentation)
3. Extract all words with bboxes
4. Batch evaluate with LangGraph
5. Enrich with bboxes
"""

import tempfile
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict

import fitz  # PyMuPDF
from rapidfuzz import fuzz

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# LangGraph imports
from langgraph.graph import StateGraph, END

from Modal.evaluations import EVALUATION_CRITERIA


from dotenv import load_dotenv
load_dotenv()  # Load .env file

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GEMINI_API_KEY,
        temperature=0
    )
    
    response = llm.invoke("Say 'API works!'")
    print(f"Response: {response.content}")
    print("✓ Gemini API is working!")
    
except Exception as e:
    print(f"✗ Error: {e}")
# ============================================================================
# LANGGRAPH STATE
# ============================================================================

class BatchEvaluationState(TypedDict):
    """State for batch evaluation workflow."""
    questions: List[Dict[str, Any]]
    full_text: str
    all_words: List[Dict[str, Any]]
    job_id: str
    
    # Evaluation results
    evaluations: List[Dict[str, Any]]
    
    # Judge results
    judge_approved: bool
    judge_feedback: Optional[str]
    retry_count: int
    max_retries: int
    
    error: Optional[str]


# ============================================================================
# EXTRACTION
# ============================================================================

def extract_questions_simple(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract questions using simple regex."""
    doc = fitz.open(pdf_path)
    full_text = "".join([page.get_text() for page in doc])
    doc.close()
    
    pattern = r'(?:Question|Q)\s*(\d+)[:\.]?\s*(.*?)(?=(?:Question|Q)\s*\d+|$)'
    matches = re.findall(pattern, full_text, re.DOTALL | re.IGNORECASE)
    
    return [
        {"q_id": f"Q{num}", "number": int(num), "text": text.strip()}
        for num, text in matches if text.strip()
    ]


def extract_full_text(pdf_path: str) -> str:
    """Extract all text from submission - no segmentation."""
    doc = fitz.open(pdf_path)
    full_text = "".join([page.get_text() for page in doc])
    doc.close()
    return full_text


def extract_all_words_with_bboxes(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract EVERY word in PDF with bbox.
    This is the key - we get positions for entire document,
    then search for phrases later.
    """
    doc = fitz.open(pdf_path)
    all_words = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if block["type"] != 0:  # Skip non-text
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    span_text = span["text"]
                    bbox = span["bbox"]
                    
                    span_words = span_text.split()
                    word_width = (bbox[2] - bbox[0]) / max(len(span_words), 1)
                    
                    for i, word in enumerate(span_words):
                        if word.strip():
                            all_words.append({
                                "text": word,
                                "bbox": {
                                    "x0": round(bbox[0] + i * word_width, 2),
                                    "y0": round(bbox[1], 2),
                                    "x1": round(bbox[0] + (i + 1) * word_width, 2),
                                    "y1": round(bbox[3], 2)
                                },
                                "page": page_num + 1
                            })
    
    doc.close()
    return all_words


# ============================================================================
# LANGCHAIN CHAINS
# ============================================================================

def create_batch_evaluation_chain():
    """LangChain chain for batch evaluation of all questions."""
    
    if not GEMINI_API_KEY:
        return None
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GEMINI_API_KEY,
        temperature=0.3
    )
    
    criteria_desc = "\n".join([
        f"- {key}: {EVALUATION_CRITERIA[key]['description']}" 
        for key in EVALUATION_CRITERIA.keys()
    ])
    
    prompt = ChatPromptTemplate.from_template("""You are evaluating a student exam submission.

QUESTIONS:
{questions}

STUDENT SUBMISSION (full text):
{submission}

AVAILABLE CRITERIA TYPES:
{criteria}

{judge_feedback}

For EACH question, you must:
1. Find where the student answered it in the submission
2. Select the most appropriate evaluation criteria type
3. Evaluate the answer against that criteria
4. Provide specific feedback with exact phrases to highlight

Return ONLY valid JSON array (one object per question):
[
  {{
    "question_number": 1,
    "selected_criteria": "science",
    "feedback": [
      {{
        "criterion": "scientific_accuracy",
        "score": 0.85,
        "highlight_phrase": "exact text from submission or null",
        "comment": "specific feedback about this criterion",
        "confidence": 0.95
      }}
    ],
    "overall_score": 0.85
  }}
]

CRITICAL RULES:
- Return array with exactly {num_questions} objects (one per question)
- highlight_phrase must be EXACT text from submission or null
- Scores are 0.0 to 1.0
- If student didn't answer a question, set overall_score to 0.0""")
    
    parser = JsonOutputParser()
    
    chain = (
        {
            "questions": lambda x: x["questions"],
            "submission": lambda x: x["submission"],
            "criteria": lambda x: criteria_desc,
            "judge_feedback": lambda x: f"\nJUDGE FEEDBACK FROM PREVIOUS ATTEMPT:\n{x['judge_feedback']}" if x.get('judge_feedback') else "",
            "num_questions": lambda x: x["num_questions"]
        }
        | prompt
        | llm
        | parser
    )
    
    return chain


def create_batch_judge_chain():
    """LangChain chain for judge validation of batch evaluation."""
    
    if not GEMINI_API_KEY:
        return None
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=GEMINI_API_KEY,
        temperature=0.1
    )
    
    prompt = ChatPromptTemplate.from_template("""You are a quality assurance judge reviewing a batch evaluation.

QUESTIONS:
{questions}

SUBMISSION:
{submission}

EVALUATIONS (array of {num_evals} evaluations):
{evaluations}

Validate:
1. Are criteria selections appropriate for each question?
2. Do scores align with answer content?
3. Are highlighted phrases actually in the submission?
4. Is feedback constructive and specific?
5. Were all {num_evals} questions evaluated?

Return ONLY valid JSON:
{{
  "approved": true/false,
  "reason": "explanation of issues or approval",
  "confidence": 0.95
}}""")
    
    parser = JsonOutputParser()
    
    chain = (
        {
            "questions": lambda x: x["questions"],
            "submission": lambda x: x["submission"],
            "evaluations": lambda x: json.dumps(x["evaluations"], indent=2),
            "num_evals": lambda x: x["num_evals"]
        }
        | prompt
        | llm
        | parser
    )
    
    return chain


# ============================================================================
# LANGGRAPH NODES
# ============================================================================

def batch_evaluate_node(state: BatchEvaluationState) -> BatchEvaluationState:
    """LangGraph node: Batch evaluate all questions."""
    
    chain = create_batch_evaluation_chain()
    
    if not chain:
        state["error"] = "No Gemini API key"
        state["evaluations"] = []
        return state
    
    try:
        # Format questions for prompt
        questions_text = "\n".join([
            f"{q['number']}. {q['text']}"
            for q in state["questions"]
        ])
        
        result = chain.invoke({
            "questions": questions_text,
            "submission": state["full_text"][:20000],  # Limit to avoid token limits
            "judge_feedback": state.get("judge_feedback"),
            "num_questions": len(state["questions"])
        })
        
        # Ensure result is a list
        if isinstance(result, list):
            state["evaluations"] = result
        else:
            state["evaluations"] = [result]
        
        # Add criteria details
        for evaluation in state["evaluations"]:
            criteria_type = evaluation.get("selected_criteria", "reasoning")
            if criteria_type in EVALUATION_CRITERIA:
                evaluation["criteria_details"] = EVALUATION_CRITERIA[criteria_type]
        
    except Exception as e:
        state["error"] = str(e)
        state["evaluations"] = []
    
    return state


def batch_judge_node(state: BatchEvaluationState) -> BatchEvaluationState:
    """LangGraph node: Judge validates batch evaluation."""
    
    chain = create_batch_judge_chain()
    
    if not chain:
        state["judge_approved"] = True
        return state
    
    try:
        questions_text = "\n".join([
            f"{q['number']}. {q['text']}"
            for q in state["questions"]
        ])
        
        result = chain.invoke({
            "questions": questions_text,
            "submission": state["full_text"][:20000],
            "evaluations": state["evaluations"],
            "num_evals": len(state["questions"])
        })
        
        state["judge_approved"] = result.get("approved", True)
        state["judge_feedback"] = result.get("reason", "") if not result.get("approved") else None
        
    except Exception as e:
        state["judge_approved"] = True
        state["judge_feedback"] = f"Judge error: {e}"
    
    return state


def retry_decision_node(state: BatchEvaluationState) -> str:
    """LangGraph node: Decide whether to retry batch evaluation."""
    
    if state["judge_approved"]:
        return "finish"
    
    if state["retry_count"] >= state["max_retries"]:
        return "finish"
    
    state["retry_count"] += 1
    return "retry"


def enrich_node(state: BatchEvaluationState) -> BatchEvaluationState:
    """LangGraph node: Enrich evaluations with bboxes."""
    
    all_words = state["all_words"]
    
    for evaluation in state["evaluations"]:
        for feedback_item in evaluation.get("feedback", []):
            phrase = feedback_item.get("highlight_phrase")
            
            if phrase:
                # Try exact match
                bbox = find_phrase_bbox(phrase, all_words)
                
                if bbox:
                    feedback_item["bbox"] = bbox
                    feedback_item["bbox_confidence"] = 1.0
                else:
                    # Try fuzzy match
                    bbox = find_phrase_bbox_fuzzy(phrase, all_words)
                    feedback_item["bbox"] = bbox
                    feedback_item["bbox_confidence"] = 0.8 if bbox else 0.0
            else:
                feedback_item["bbox"] = None
                feedback_item["bbox_confidence"] = 0.0
    
    return state


# ============================================================================
# LANGGRAPH WORKFLOW
# ============================================================================

def create_batch_evaluation_graph():
    """Create LangGraph workflow for batch evaluation."""
    
    workflow = StateGraph(BatchEvaluationState)
    
    # Add nodes
    workflow.add_node("evaluate", batch_evaluate_node)
    workflow.add_node("judge", batch_judge_node)
    workflow.add_node("enrich", enrich_node)
    
    # Define edges
    workflow.set_entry_point("evaluate")
    workflow.add_edge("evaluate", "judge")
    workflow.add_conditional_edges(
        "judge",
        retry_decision_node,
        {
            "retry": "evaluate",  # Loop back
            "finish": "enrich"
        }
    )
    workflow.add_edge("enrich", END)
    
    return workflow.compile()


# ============================================================================
# MAIN PROCESS
# ============================================================================

def process(questionnaire_content: bytes, submission_content: bytes, job_id: str,
            questionnaire_filename: str, submission_filename: str) -> dict:
    """Main entry point using batch evaluation."""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_q:
        temp_q_path = temp_q.name
        temp_q.write(questionnaire_content)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_s:
        temp_s_path = temp_s.name
        temp_s.write(submission_content)

    try:
        # Extract questions
        questions = extract_questions_simple(temp_q_path)
        
        # Extract full text (no answer segmentation!)
        full_text = extract_full_text(temp_s_path)
        
        # Extract all words with bboxes
        all_words = extract_all_words_with_bboxes(temp_s_path)
        
        # Run batch evaluation with LangGraph
        evaluations = evaluate_batch_with_langgraph(
            questions, full_text, all_words, job_id
        )
        
        # Build QA pairs for compatibility
        qa_pairs = []
        for i, question in enumerate(questions):
            qa_pairs.append({
                "question": question,
                "answer": {"text": "[Answer extracted by LLM from full text]"},
                "confidence": 1.0,
                "match_method": "llm_batch"
            })

        return {
            "job_id": job_id,
            "status": "done",
            "questionnaire_filename": questionnaire_filename,
            "submission_filename": submission_filename,
            "question_count": len(questions),
            "answer_count": len(questions),  # Same as questions
            "matched_pairs": len(questions),
            "needs_review_count": sum(
                1 for e in evaluations 
                if not e.get("judge_approved", True) or 
                   any(f.get("bbox") is None and f.get("highlight_phrase") for f in e.get("feedback", []))
            ),
            "qa_pairs": qa_pairs,
            "evaluations": evaluations,
        }

    finally:
        Path(temp_q_path).unlink(missing_ok=True)
        Path(temp_s_path).unlink(missing_ok=True)


def evaluate_batch_with_langgraph(questions: List[Dict], full_text: str, 
                                   all_words: List[Dict], job_id: str) -> List[Dict]:
    """Evaluate all questions in batch using LangGraph."""
    
    graph = create_batch_evaluation_graph()
    
    # Initialize state
    initial_state = {
        "questions": questions,
        "full_text": full_text,
        "all_words": all_words,
        "job_id": job_id,
        "evaluations": [],
        "judge_approved": False,
        "judge_feedback": None,
        "retry_count": 0,
        "max_retries": 1,  # Reduced from 2 to save costs
        "error": None
    }
    
    # Run workflow
    final_state = graph.invoke(initial_state)
    
    # Add metadata to evaluations
    evaluations = final_state["evaluations"]
    for i, evaluation in enumerate(evaluations):
        q_num = evaluation.get("question_number", i + 1)
        evaluation.update({
            "id": f"eval-{job_id[:8]}-{q_num:03d}",
            "qa_pair_id": f"Q{q_num}",
            "judge_approved": final_state["judge_approved"],
            "retry_count": final_state["retry_count"],
            "needs_review": (
                not final_state["judge_approved"] or
                any(f.get("bbox") is None and f.get("highlight_phrase") for f in evaluation.get("feedback", []))
            ),
            "error": final_state.get("error")
        })
    
    return evaluations


# ============================================================================
# BBOX HELPERS
# ============================================================================

def find_phrase_bbox(phrase: str, words: List[Dict]) -> Optional[Dict]:
    """Find exact phrase and compute combined bbox."""
    phrase_words = phrase.lower().split()
    
    for i in range(len(words) - len(phrase_words) + 1):
        window = words[i:i + len(phrase_words)]
        window_text = [w["text"].lower() for w in window]
        
        if window_text == phrase_words:
            return {
                "x0": min(w["bbox"]["x0"] for w in window),
                "y0": min(w["bbox"]["y0"] for w in window),
                "x1": max(w["bbox"]["x1"] for w in window),
                "y1": max(w["bbox"]["y1"] for w in window),
                "page": window[0]["page"]
            }
    
    return None


def find_phrase_bbox_fuzzy(phrase: str, words: List[Dict]) -> Optional[Dict]:
    """Fuzzy match phrase with 80% similarity threshold."""
    phrase_lower = phrase.lower()
    best_match = None
    best_score = 0
    
    for size in range(1, min(20, len(words))):
        for i in range(len(words) - size + 1):
            window = words[i:i + size]
            candidate = " ".join([w["text"] for w in window])
            score = fuzz.ratio(phrase_lower, candidate.lower())
            
            if score > best_score and score > 80:
                best_score = score
                best_match = window
    
    if best_match:
        return {
            "x0": min(w["bbox"]["x0"] for w in best_match),
            "y0": min(w["bbox"]["y0"] for w in best_match),
            "x1": max(w["bbox"]["x1"] for w in best_match),
            "y1": max(w["bbox"]["y1"] for w in best_match),
            "page": best_match[0]["page"]
        }
    
    return None