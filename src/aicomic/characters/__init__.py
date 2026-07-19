"""Character consistency system — character creation, storage, prompt injection,
workshop tools, consistency checking, and four-view generation."""

from aicomic.characters.character_views import (
    CharacterView,
    FourViewGenerator,
    FourViewSet,
    ViewAngle,
    ensure_views_schema,
    generate_four_view_prompts,
    generate_view_prompt,
    get_negative_prompt_for_angle,
)
from aicomic.characters.character_workshop import (
    CharacterVariant,
    CharacterWorkshop,
    ExtractionResult,
    ensure_workshop_schema,
)
from aicomic.characters.consistency_service import (
    AttributeEntry,
    ConsistencyIssue,
    ConsistencyReport,
    ConsistencyService,
    CorrectionSuggestion,
    ShotCharacterState,
    ensure_consistency_schema,
    extract_attributes,
)
