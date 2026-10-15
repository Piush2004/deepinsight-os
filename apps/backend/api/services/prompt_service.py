import os
import hashlib
from typing import Dict, Any

class PromptService:
    """
    Manages loading and versioning of file-based prompts.
    """
    def __init__(self, base_dir: str = "prompts"):
        self.base_dir = base_dir

    def load_prompt(self, agent_name: str, template_name: str, context: Dict[str, Any] = None) -> str:
        """
        Loads a prompt template from disk and injects context.
        Example: load_prompt("reporting", "executive_summary.md", {"brand_voice": "..."})
        """
        prompt_path = os.path.join(self.base_dir, agent_name, f"{template_name}.md")
        
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
            
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        if context:
            try:
                # Basic python formatting, in production use Jinja2 for safer/complex templating
                template = template.format(**context)
            except KeyError as e:
                # Handle missing keys gracefully or let it raise depending on strictness
                raise ValueError(f"Missing context variable for prompt: {e}")
                
        return template

    def get_prompt_version_hash(self, agent_name: str, template_name: str) -> str:
        """Returns the SHA256 hash of the prompt file to track versioning in logs."""
        prompt_path = os.path.join(self.base_dir, agent_name, f"{template_name}.md")
        if not os.path.exists(prompt_path):
            return "unknown"
            
        with open(prompt_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
