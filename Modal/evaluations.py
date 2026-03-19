 
from typing import Dict, List, Any


EVALUATION_CRITERIA = {
    # SCIENCE
    "science": {
        "name": "Science Questions",
        "description": "Biology, Chemistry, Physics, General Science",
        "criteria": [
            {
                "id": "scientific_accuracy",
                "name": "Scientific Accuracy",
                "weight": 40,
                "guidance": "Correct scientific facts, laws, and principles. No misconceptions or errors.",
                "levels": ["Incorrect", "Partially Correct", "Mostly Correct", "Fully Correct"]
            },
            {
                "id": "terminology",
                "name": "Scientific Terminology",
                "weight": 20,
                "guidance": "Proper use of scientific terms, units, and notation.",
                "levels": ["Poor", "Basic", "Good", "Excellent"]
            },
            {
                "id": "explanation_clarity",
                "name": "Explanation Clarity",
                "weight": 25,
                "guidance": "Clear explanation of scientific concepts and processes.",
                "levels": ["Unclear", "Somewhat Clear", "Clear", "Very Clear"]
            },
            {
                "id": "completeness",
                "name": "Completeness",
                "weight": 15,
                "guidance": "All parts of the question addressed with sufficient detail.",
                "levels": ["Incomplete", "Partially Complete", "Complete", "Comprehensive"]
            }
        ]
    },
    
    # MATH
    "math": {
        "name": "Mathematics Questions",
        "description": "Calculations, proofs, problem-solving, algebra, calculus",
        "criteria": [
            {
                "id": "mathematical_correctness",
                "name": "Mathematical Correctness",
                "weight": 50,
                "guidance": "Correct formulas, calculations, and final answer.",
                "levels": ["Wrong", "Minor Errors", "Mostly Correct", "Fully Correct"]
            },
            {
                "id": "logical_steps",
                "name": "Logical Steps & Working",
                "weight": 35,
                "guidance": "Shows clear step-by-step working. Each step follows logically.",
                "levels": ["Missing/Illogical", "Some Steps", "Clear Steps", "Comprehensive Steps"]
            },
            {
                "id": "notation_format",
                "name": "Mathematical Notation",
                "weight": 15,
                "guidance": "Proper mathematical symbols, units, and formatting.",
                "levels": ["Poor", "Basic", "Good", "Excellent"]
            }
        ]
    },
    
    # DIAGRAMS AND GRAPHS
    "diagrams_graphs": {
        "name": "Diagrams and Graphs",
        "description": "Visual representations, charts, plots, labeled diagrams",
        "criteria": [
            {
                "id": "accuracy",
                "name": "Visual Accuracy",
                "weight": 35,
                "guidance": "Diagram/graph correctly represents the concept or data.",
                "levels": ["Inaccurate", "Partially Accurate", "Mostly Accurate", "Fully Accurate"]
            },
            {
                "id": "labeling",
                "name": "Labeling & Annotations",
                "weight": 25,
                "guidance": "All parts properly labeled with clear, readable text.",
                "levels": ["Missing/Poor", "Incomplete", "Complete", "Comprehensive"]
            },
            {
                "id": "clarity",
                "name": "Visual Clarity",
                "weight": 20,
                "guidance": "Clear, neat, and easy to interpret. Good use of space.",
                "levels": ["Unclear", "Somewhat Clear", "Clear", "Very Clear"]
            },
            {
                "id": "completeness",
                "name": "Completeness",
                "weight": 20,
                "guidance": "All required elements included (axes, legend, units, scale).",
                "levels": ["Incomplete", "Partially Complete", "Complete", "Fully Complete"]
            }
        ]
    },
    
    # MULTILINGUAL

    "multilingual": {
        "name": "Multilingual Questions",
        "description": "Non-English submissions or translation tasks",
        "criteria": [
            {
                "id": "language_accuracy",
                "name": "Language Accuracy",
                "weight": 35,
                "guidance": "Correct grammar, vocabulary, and syntax in target language.",
                "levels": ["Poor", "Fair", "Good", "Excellent"]
            },
            {
                "id": "content_accuracy",
                "name": "Content Accuracy",
                "weight": 35,
                "guidance": "Factually correct answer regardless of language.",
                "levels": ["Incorrect", "Partially Correct", "Mostly Correct", "Fully Correct"]
            },
            {
                "id": "comprehension",
                "name": "Question Comprehension",
                "weight": 15,
                "guidance": "Student understood the question correctly.",
                "levels": ["Misunderstood", "Partial Understanding", "Good Understanding", "Full Understanding"]
            },
            {
                "id": "expression",
                "name": "Clarity of Expression",
                "weight": 15,
                "guidance": "Ideas clearly expressed in the target language.",
                "levels": ["Unclear", "Somewhat Clear", "Clear", "Very Clear"]
            }
        ]
    },
    

    # REASONING

    "reasoning": {
        "name": "Reasoning & Critical Thinking",
        "description": "Analysis, evaluation, argumentation, problem-solving",
        "criteria": [
            {
                "id": "logical_reasoning",
                "name": "Logical Reasoning",
                "weight": 35,
                "guidance": "Arguments are logical, coherent, and well-structured.",
                "levels": ["Illogical", "Weak Logic", "Sound Logic", "Strong Logic"]
            },
            {
                "id": "evidence_support",
                "name": "Evidence & Support",
                "weight": 30,
                "guidance": "Claims supported with relevant evidence, examples, or data.",
                "levels": ["No Support", "Weak Support", "Good Support", "Strong Support"]
            },
            {
                "id": "critical_analysis",
                "name": "Critical Analysis",
                "weight": 25,
                "guidance": "Goes beyond description. Shows analysis, evaluation, synthesis.",
                "levels": ["Descriptive Only", "Some Analysis", "Good Analysis", "Deep Analysis"]
            },
            {
                "id": "conclusion",
                "name": "Conclusion Quality",
                "weight": 10,
                "guidance": "Well-reasoned conclusion that follows from the argument.",
                "levels": ["Weak/Missing", "Basic", "Good", "Strong"]
            }
        ]
    },
    

    # REPORT
    "report": {
        "name": "Report Writing",
        "description": "Lab reports, research papers, formal documents",
        "criteria": [
            {
                "id": "structure_organization",
                "name": "Structure & Organization",
                "weight": 25,
                "guidance": "Clear sections (intro, methods, results, conclusion). Logical flow.",
                "levels": ["Poor Structure", "Basic Structure", "Good Structure", "Excellent Structure"]
            },
            {
                "id": "content_accuracy",
                "name": "Content Accuracy",
                "weight": 30,
                "guidance": "Accurate data, correct methodology, valid conclusions.",
                "levels": ["Inaccurate", "Partially Accurate", "Mostly Accurate", "Fully Accurate"]
            },
            {
                "id": "analysis_interpretation",
                "name": "Analysis & Interpretation",
                "weight": 25,
                "guidance": "Proper analysis of data/results. Meaningful interpretation.",
                "levels": ["Weak", "Basic", "Good", "Strong"]
            },
            {
                "id": "presentation_format",
                "name": "Presentation & Format",
                "weight": 20,
                "guidance": "Professional formatting, clear tables/figures, proper citations.",
                "levels": ["Poor", "Fair", "Good", "Excellent"]
            }
        ]
    }
}
 
 
# HELPER FUNCTIONS
 
def get_criteria(category: str) -> Dict[str, Any]:
    return EVALUATION_CRITERIA.get(category)

# print(get_criteria("math"))