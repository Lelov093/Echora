"""ReviewCommitNode — summarizes candidates, ensures nothing auto-commits.

All candidates stay in pending state. User action required via API.
"""

from app.agents.state import ConversationAgentState


def review_commit_node(state: ConversationAgentState) -> ConversationAgentState:
    state.setdefault("trace_steps", []).append({
        "step": "review_commit",
        "order": 8,
        "status": "completed",
        "message": "Candidates held pending — awaiting user review",
        "memory_candidates_count": len(state.get("memory_candidates", [])),
        "presence_opportunities_count": len(state.get("presence_opportunities", [])),
        "auto_committed": False,
    })
    return state
