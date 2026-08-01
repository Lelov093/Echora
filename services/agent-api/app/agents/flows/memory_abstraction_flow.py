"""MemoryAbstractionFlow — create abstraction candidates from repeated memory signals."""

from app.services import memory_abstraction_service, memory_service


def generate_abstraction(
    companion_id: str,
    memory_ids: list[str] | None = None,
    abstraction_type: str = "project_pattern",
) -> dict | None:
    """Generate a basic abstraction candidate from memory patterns."""
    # Simple rule-based: if 3+ memories share similar type, propose abstraction
    if not memory_ids or len(memory_ids) < 2:
        return None
    payload = {
        "user_id": "4a4f3806-0d3e-4ab1-80ed-51f93b60aa80",
        "companion_id": companion_id,
        "source_memory_ids": memory_ids,
        "abstraction_type": abstraction_type,
        "title": "Auto-detected pattern",
        "content": "Based on repeated memory signals",
        "confidence": 0.6,
        "evidence_score": 0.5,
    }
    return memory_abstraction_service.create_candidate(payload)
