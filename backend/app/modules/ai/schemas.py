"""AI request bodies and structured-output schemas (spec §9.3, §9.6).

Output schemas avoid defaults and constraints so they work with strict JSON-schema structured outputs.
Business limits are enforced in post-processing instead.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common import enums
from app.common.pagination import PageParams
from app.common.validation import OptText, StrictModel, Text

# Requests -----------------------------------------------------------------------------------


class ChatContext(StrictModel):
    type: Literal["harness", "idea", "resource", "collection"]
    id: uuid.UUID


class ChatRequest(StrictModel):
    conversation_id: uuid.UUID | None = None
    message: Text(1, 100_000)
    context: ChatContext | None = None


class ConversationPatch(StrictModel):
    title: Text(1, 120)


class GenerateHarnessBody(StrictModel):
    repo_url: Text(1, 2048)
    additional_context: OptText(4000) = None


class GenerateIdeaBody(StrictModel):
    domain: OptText(300) = None
    problem: OptText(2000) = None
    tech_preferences: list[Text(1, 50)] = Field(default_factory=list, max_length=15)
    interests: OptText(1000) = None
    count: int = Field(1, ge=1, le=3)

    @model_validator(mode="after")
    def _need_one(self):
        if not (self.domain or self.problem or self.interests):
            raise ValueError("Provide at least one of domain, problem, or interests.")
        return self


class GenerateResourcesBody(StrictModel):
    topic: Text(2, 200)
    goal: OptText(500) = None
    level: Literal["beginner", "intermediate", "advanced"] | None = None


class RefineBody(StrictModel):
    text: Text(1, 20000)
    action: Literal[tuple(enums.AI_REFINE_ACTIONS)]  # type: ignore[valid-type]
    instruction: OptText(500) = None
    field: Text(1, 100)

    @model_validator(mode="after")
    def _custom_needs_instruction(self):
        if self.action == "custom" and not self.instruction:
            raise ValueError("instruction is required when action is 'custom'.")
        return self


class FeedbackBody(StrictModel):
    target_type: Literal["harness", "idea"]
    target_id: uuid.UUID


class DraftsQuery(PageParams):
    task: Literal[tuple(enums.AI_DRAFT_TASKS)] | None = None  # type: ignore[valid-type]
    status: Literal["draft", "published", "discarded"] | None = "draft"


class DraftPatch(StrictModel):
    output: dict


class RefineSectionBody(StrictModel):
    field: Text(1, 100)
    instruction: Text(1, 500)


class RegenerateDraftBody(StrictModel):
    additional_context: OptText(4000) = None


class RestoreBody(StrictModel):
    history_index: int = Field(ge=0, le=9)


# Structured outputs --------------------------------------------------------------------------


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


ComponentTypeLit = Literal[tuple(enums.COMPONENT_TYPES)]  # type: ignore[valid-type]


class Component(_Out):
    type: ComponentTypeLit
    name: str
    description: str
    evidence_path: str | None


class HarnessDocDraft(_Out):
    name: str
    short_description: str
    problem_addressed: str
    detailed_explanation: str
    architecture: str
    components: list[Component]
    setup_instructions: str
    limitations: str
    suggested_tools: list[str]
    suggested_category: str
    suggested_tags: list[str]
    gaps_and_uncertainties: list[str]


class Feature(_Out):
    title: str
    detail: str


class ProjectIdeaDraft(_Out):
    title: str
    summary: str
    problem_statement: str
    proposed_solution: str
    target_users: str
    expected_features: list[Feature]
    tech_stack: list[str]
    architecture: str
    milestones: list[str]
    challenges: list[str]
    suggested_category: str
    suggested_tags: list[str]


class ProjectIdeaDrafts(_Out):
    ideas: list[ProjectIdeaDraft]


class ModelRecommendation(_Out):
    name: str
    url: str | None
    hub_resource_id: str | None
    description: str
    resource_type: str
    category: str
    level: str


class ResourceRecommendations(_Out):
    learning_path_notes: str
    recommendations: list[ModelRecommendation]


class RefineOutput(_Out):
    text: str
    change_summary: str


class SectionOutput(_Out):
    value: str


class FeedbackSuggestion(_Out):
    category: Literal[tuple(enums.AI_FEEDBACK_CATEGORIES)]  # type: ignore[valid-type]
    title: str
    detail: str
    confidence: Literal["low", "medium", "high"]
    based_on: list[str]


class FeedbackOutput(_Out):
    suggestions: list[FeedbackSuggestion]


# Stored draft outputs (validated on PATCH) -------------------------------------------------


class VerifiedRecommendation(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: int
    name: str
    url: str
    description: str = ""
    resource_type: str = "other"
    category: str | None = None
    level: str | None = None
    source: Literal["knowledge_hub", "model"]
    hub_resource_id: str | None = None
    verification: dict


class StoredRecommendations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learning_path_notes: str
    recommendations: list[VerifiedRecommendation]
    omitted: list[dict] = Field(default_factory=list)


class StoredFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    suggestions: list[FeedbackSuggestion]


DRAFT_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "harness_doc": HarnessDocDraft,
    "project_idea": ProjectIdeaDrafts,
    "resource_recommendations": StoredRecommendations,
    "feedback_suggestions": StoredFeedback,
}
