import time
from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    The BaseAgent SDK.
    All future AI agents in DeepInsight OS MUST inherit from this class.
    It strictly enforces the orchestration lifecycle and ensures consistent state management,
    validation, and observability out of the box.
    """
    
    def __init__(self, client_id: UUID, task_id: UUID, **kwargs: Any):
        self.client_id = client_id
        self.task_id = task_id
        self.context: Dict[str, Any] = {}
        self.output: Any = None
        self.is_approved: bool = False
        self.execution_logs: Dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "duration": None,
            "errors": []
        }
        
    def run(self, **kwargs: Any) -> Any:
        """
        The Template Method defining the strict agent lifecycle.
        Child classes should not override this method directly.
        """
        self.execution_logs["start_time"] = time.time()
        try:
            self.initialize(**kwargs)
            self.validate()
            self.gather_context()
            self.output = self.execute()
            self.validate_output()
            
            # Workflow pause point for human-in-the-loop if required by the implementation
            if self.requires_human_approval():
                self.request_approval()
                
            self.finalize()
        except Exception as e:
            self.execution_logs["errors"].append(str(e))
            logger.error(f"Agent Execution Failed: {e}")
            raise
        finally:
            self.execution_logs["end_time"] = time.time()
            self.execution_logs["duration"] = self.execution_logs["end_time"] - self.execution_logs["start_time"]
            self.audit()
            
        return self.output

    @abstractmethod
    def initialize(self, **kwargs: Any) -> None:
        """Setup initial state, parse arguments, and configure the agent."""
        pass

    @abstractmethod
    def validate(self) -> None:
        """Validate input parameters and preconditions before starting work."""
        pass

    @abstractmethod
    def gather_context(self) -> None:
        """
        Query the Knowledge Base (or Domain Service) to populate self.context.
        No execution or LLM generation happens here.
        """
        pass

    @abstractmethod
    def execute(self) -> Any:
        """
        The core generation or reasoning loop.
        Uses self.context to interact with the LLMProviderInterface.
        Returns the raw generated output.
        """
        pass

    @abstractmethod
    def validate_output(self) -> None:
        """Validate the generated output (e.g., check schemas, hallucination checks)."""
        pass
        
    def requires_human_approval(self) -> bool:
        """Override to return True if the agent requires human intervention."""
        return False

    def request_approval(self) -> None:
        """Pause or trigger an event for approval queue logic."""
        pass

    @abstractmethod
    def finalize(self) -> None:
        """Persist results, send webhooks, or trigger downstream actions."""
        pass

    def audit(self) -> None:
        """
        Standardized observability logging.
        Persists timing, tokens, prompts, and errors to the AuditLog database.
        """
        logger.info(
            f"Agent Audit - Client: {self.client_id} | Task: {self.task_id} | "
            f"Duration: {self.execution_logs['duration']:.2f}s | Errors: {len(self.execution_logs['errors'])}"
        )
        # Note: In a full implementation, this will write to the AuditLog database model.
