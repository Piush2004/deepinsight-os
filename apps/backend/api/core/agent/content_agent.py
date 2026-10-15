from typing import Any
from uuid import UUID
from api.core.agent.base import BaseAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer
from api.services.validation.brand_voice import BrandVoiceValidator
from api.services.validation.content_quality import ContentQualityEngine

class ContentAgent(BaseAgent):
    """
    The Content Intelligence Agent.
    Generates structured, brand-compliant marketing content.
    """
    
    def __init__(
        self,
        client_id: UUID,
        task_id: UUID,
        llm: LLMProvider,
        knowledge_query: KnowledgeQueryService,
        prompt_service: PromptService,
        intelligence: IntelligenceLayer,
        quality_engine: ContentQualityEngine,
        db=None,
        **kwargs: Any
    ):
        super().__init__(client_id, task_id, **kwargs)
        self.llm = llm
        self.knowledge_query = knowledge_query
        self.prompt_service = prompt_service
        self.intelligence = intelligence
        self.quality_engine = quality_engine
        self.db = db

        self.content_type = None
        self.target_audience = None
        self.goal = None
        self.content_id = None  # set to edit/version an existing Content row
        self.title = None
        self.content = None  # set in finalize() once persisted

    def initialize(self, **kwargs: Any) -> None:
        self.content_type = kwargs.get("content_type")
        self.target_audience = kwargs.get("target_audience")
        self.goal = kwargs.get("goal")
        self.content_id = kwargs.get("content_id")
        self.title = kwargs.get("title")
        self.execution_logs["agent"] = "ContentAgent"
        
    def validate(self) -> None:
        if not self.content_type:
            raise ValueError("Content type is required.")
            
    def gather_context(self) -> None:
        """
        Retrieves Brand Voice and Business Context, passes it to the Intelligence Layer.
        """
        # Retrieve raw context
        raw_knowledge = {
            "brand_voice": self.knowledge_query.query("What is the brand voice and required keywords?", self.client_id),
            "audience": self.knowledge_query.query(f"What do we know about {self.target_audience}?", self.client_id),
            "goal": self.goal
        }
        
        # Transform via Intelligence Layer
        self.context["intelligence"] = self.intelligence.generate_context({}, raw_knowledge)
        self.context["brand_voice"] = raw_knowledge["brand_voice"]
        # goal/audience were computed into raw_knowledge above but never actually
        # copied onto self.context, which is what prompt_service.load_prompt()
        # str.format()s against - the "goal" prompts/content/*.md templates reference
        # were raising "Missing context variable for prompt: 'goal'" on every real
        # content-generation call before this fix, never caught because the unit test
        # suite constructs self.context directly rather than exercising gather_context().
        self.context["goal"] = self.goal
        self.context["audience"] = raw_knowledge["audience"]

    def execute(self) -> Any:
        """
        Loads the specific content prompt, generates content.
        """
        prompt_name = self.content_type.lower().replace(" ", "_")
        exec_hash = self.prompt_service.get_prompt_version_hash("content", prompt_name)
        self.execution_logs["prompt_version"] = exec_hash
        
        exec_prompt = self.prompt_service.load_prompt("content", prompt_name, self.context)
        
        system_prompt = "You are a world-class marketing copywriter."
        generated_text = self.llm.generate(exec_prompt, system_prompt=system_prompt)
        
        return {
            "body": generated_text,
            "content_type": self.content_type
        }
        
    def validate_output(self) -> None:
        """
        Enforces Brand Voice and calculates Content Scores.
        """
        brand_rules = self.context["brand_voice"].get("content", {})
        if isinstance(brand_rules, str):
            # Fallback if raw text
            brand_rules = {"forbidden_terms": [], "required_keywords": []}
            
        validator = BrandVoiceValidator(brand_rules)
        validation_result = validator.validate(self.output["body"])
        
        if not validation_result["passed"]:
            errors = "; ".join(validation_result["errors"])
            raise ValueError(f"Brand Voice Validation Failed: {errors}")
            
        # Score Content
        scores = self.quality_engine.score_content(self.output["body"], self.context)
        self.output["scores"] = scores
        
        if scores["overall_score"] < 80:
             raise ValueError(f"Content Quality Score too low: {scores['overall_score']}")
            
    def requires_human_approval(self) -> bool:
        return True
        
    def request_approval(self) -> None:
        self.is_approved = False
        
    def finalize(self) -> None:
        """Persists the generated draft as a new Content row (or a new ContentVersion
        on an existing one, when content_id was supplied) plus its ContentScore, and
        opens a ContentApprovalRequest so it lands in the approval queue."""
        if self.db is None:
            return  # unit-test / dry-run mode with no DB session provided

        import uuid as uuid_module
        from api.models.content import Content, ContentVersion, ContentScore, ContentApprovalRequest

        if self.content_id:
            content_uuid = uuid_module.UUID(self.content_id) if isinstance(self.content_id, str) else self.content_id
            content = self.db.query(Content).filter(Content.id == content_uuid).first()
            if not content:
                raise ValueError(f"Content {self.content_id} not found for versioning.")
            next_version_number = (
                self.db.query(ContentVersion).filter(ContentVersion.content_id == content.id).count()
            ) + 1
        else:
            content = Content(
                client_id=self.client_id,
                title=self.title or f"{self.content_type} draft",
                content_type=self.content_type,
                status="pending_review",
            )
            self.db.add(content)
            self.db.flush()
            next_version_number = 1

        version = ContentVersion(
            content_id=content.id,
            version=next_version_number,
            body=self.output["body"],
            ai_model=getattr(self.llm, "model", self.llm.__class__.__name__),
            prompt_version=self.execution_logs.get("prompt_version"),
        )
        self.db.add(version)
        self.db.flush()

        scores = self.output.get("scores", {})
        self.db.add(ContentScore(
            version_id=version.id,
            originality=scores.get("originality", 0.0),
            readability=scores.get("readability", 0.0),
            grammar=scores.get("grammar", 0.0),
            professional_tone=scores.get("professional_tone", 0.0),
            brand_consistency=scores.get("brand_consistency", 0.0),
            citation_coverage=scores.get("citation_coverage", 0.0),
            hallucination_risk=scores.get("hallucination_risk", 0.0),
            completeness=scores.get("completeness", 0.0),
            overall_score=scores.get("overall_score", 0.0),
        ))

        content.status = "pending_review"
        self.db.add(content)
        self.db.add(ContentApprovalRequest(content_id=content.id, status="pending"))
        self.db.commit()

        self.content = content
