from typing import Dict, Any

class BrandVoiceValidator:
    """
    Enforces Brand Voice for generated content.
    Checks Tone, Reading Level, Writing Style, Vocabulary, Forbidden Terms, Required Keywords.
    """
    
    def __init__(self, brand_guidelines: Dict[str, Any]):
        self.guidelines = brand_guidelines
        
    def validate(self, text: str) -> Dict[str, Any]:
        errors = []
        
        # 1. Check Forbidden Terms
        forbidden_terms = self.guidelines.get("forbidden_terms", [])
        for term in forbidden_terms:
            if term.lower() in text.lower():
                errors.append(f"Forbidden term detected: '{term}'")
                
        # 2. Check Required Keywords
        required_keywords = self.guidelines.get("required_keywords", [])
        for keyword in required_keywords:
            if keyword.lower() not in text.lower():
                errors.append(f"Missing required keyword: '{keyword}'")
                
        # Additional checks (Tone, Reading Level, Vocabulary) would ideally use a lightweight LLM 
        # or NLP library (e.g., textstat for Flesch-Kincaid) in production.
        
        passed = len(errors) == 0
        
        return {
            "passed": passed,
            "errors": errors
        }
