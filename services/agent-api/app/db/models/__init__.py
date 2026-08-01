"""All Core conversation through Companion ORM models.

Import order respects FK dependency: users → companions → conversations → messages → ...
Continuity models follow Core conversation models.
"""

# ── Core conversation ──────────────────────────────────────────────────────────────────
from app.db.models.user import User
from app.db.models.companion import Companion, CompanionMode
from app.db.models.data_rights import (
    CompanionDeletionRequest,
    CompanionDeletionScopeRow,
    ConversationDeletionProof,
)
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.memory import Memory, MemoryCandidate
from app.db.models.companion_context_document import MemoryContentRevision, CompanionContextDocument
from app.db.models.memory_edge import MemoryEdge
from app.db.models.growth import GrowthCandidate, GrowthRecord
from app.db.models.relationship import (
    RelationshipCandidate,
    RelationshipEvent,
    RelationshipState,
    RelationshipStateRevision,
)
from app.db.models.affect import CompanionAffectEvent, CompanionAffectState
from app.db.models.presence import PresenceOpportunity
from app.db.models.presence_schedule import PresenceSchedule, PresenceScheduleOccurrence
from app.db.models.settings import BoundarySetting
from app.db.models.trace import TraceRun, TraceStep
from app.db.models.context import ProjectContext, CreativeContext
from app.db.models.bad_case import BadCase

# ── Continuity ──────────────────────────────────────────────────────────────────
from app.db.models.feedback_event import FeedbackEvent
from app.db.models.memory_usage_event import MemoryUsageEvent
from app.db.models.memory_lifecycle_event import MemoryLifecycleEvent
from app.db.models.memory_abstraction_candidate import MemoryAbstractionCandidate
from app.db.models.continuity_snapshot import ContinuitySnapshot
from app.db.models.user_state_snapshot import UserStateSnapshot
from app.db.models.relationship_explanation_event import RelationshipExplanationEvent
from app.db.models.review_batch import ReviewBatch
from app.db.models.chronicle_summary import CompanionChronicleSummary

# Agent execution
from app.db.models.tool import (
    ToolDefinition,
    ToolPermission,
    ToolRun,
    ToolRunStep,
    ToolRunArtifact,
    ToolResource,
)
from app.db.models.file_context import (
    FileSource,
    FileDocument,
    FileChunk,
    FileContextUsage,
)
from app.db.models.project import (
    ProjectMilestone,
    ProjectTask,
    ProjectTaskEvent,
    ProjectTaskEvidenceLink,
)
from app.db.models.conversation_task import (
    ConversationTaskRun,
    ConversationTaskStep,
    ConversationTaskStepAttempt,
    ConversationTaskPlanRevision,
)
from app.db.models.replay import AgentRunReplay, TraceReplaySession, ReplayAnnotation
from app.db.models.bad_case_inbox import (
    BadCaseInboxItem,
    BadCaseLink,
    BadCaseTriageEvent,
    BadCaseCluster,
)
from app.db.models.evaluation import (
    EvaluationDataset,
    EvaluationCase,
    EvaluationRun,
    EvaluationResult,
    EvaluationMetric,
)
from app.db.models.regression import RegressionCase, RegressionRun, RegressionResult
from app.db.models.provider import (
    LlmProviderConfig,
    LlmModelConfig,
    PromptVersion,
    LlmCallRecord,
    FallbackEvent,
)
from app.db.models.strategy import (
    RerankerTrainingExample,
    MemoryRerankerRun,
    PresencePolicyFeedbackSample,
    PresencePolicyRun,
)
from app.db.models.evidence import (
    EvidenceSufficiencyEvent,
    GrowthConsistencyCheck,
    OutdatedMemoryFlag,
    OutdatedMemoryReview,
)
from app.db.models.companion_identity import (
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    CompanionBoundaryProfile,
    CompanionVisibilityPolicy,
    CompanionLifecycleEvent,
)
from app.db.models.companion_memory import (
    CompanionMemoryScope,
    CompanionPrivateMemoryLink,
    RelationshipMemoryLink,
    SharedEpisodicMemory,
    SharedMemoryCandidate,
    SharedMemoryParticipant,
    CrossCompanionMemoryEvent,
    CrossCompanionMemoryReview,
    PrivateToSharedMemoryReview,
    SharedToPrivateMemoryReview,
)
from app.db.models.co_presence import (
    CoPresenceSession,
    CoPresenceParticipant,
    CoPresenceSessionPolicy,
    ParticipantAwarenessState,
    ParticipantMemoryPermission,
)
from app.db.models.companion_room import (
    CompanionRoomMembershipEvent,
    CompanionRoomTurn,
    CompanionRoomTurnStep,
    DiscordGuild,
    DiscordTextChannel,
    DiscordChannelBotMembership,
    DiscordChannelRoomBinding,
    DiscordChannelIngress,
    DiscordChannelDelivery,
)
from app.db.models.shared_scene import (
    SharedScene,
    SharedSceneEvent,
    SharedExperienceRecord,
)
from app.db.models.persona_growth import (
    CompanionPersonaGrowthCandidate,
    CompanionPersonaGrowthEvent,
    CompanionPersonaDriftCheck,
    GroupPersonaConsistencyCheck,
)
from app.db.models.companion_presence import (
    MutualPresencePolicyRun,
    CompanionPresenceOpportunity,
    CoPresenceOpportunity,
    CompanionPresenceFeedbackEvent,
)
from app.db.models.realtime_copresence import (
    RealtimeCoPresenceSession,
    RealtimeCoPresenceParticipant,
    RealtimeParticipantState,
    RealtimeSessionChannel,
    RealtimeSessionStateEvent,
    RealtimeChannelStateEvent,
)
from app.db.models.companion_voice import (
    VoiceProviderConfig,
    CompanionVoiceProfile,
    CompanionVoiceSession,
    VoiceTurn,
    SttEvent,
    TtsEvent,
    TurnTakingEvent,
    VoiceInterruptionEvent,
    VoicePersonaGuardRun,
)
from app.db.models.multimodal_permission import (
    MultimodalContextEvent,
    ImageContextEvent,
    ScreenContextEvent,
    FileContextRealtimeEvent,
    DeviceContextEvent,
    ParticipantContextPermission,
    ContextRetentionPolicy,
    EphemeralContextExpiryEvent,
)
from app.db.models.realtime_memory import (
    RealtimeMemoryBuffer,
    RealtimeMemoryBufferItem,
    CompanionPrivateRealtimeBuffer,
    CoPresenceSessionBuffer,
    SharedSceneBuffer,
    SalientMoment,
    CompanionPrivateSalientMoment,
    SharedSalientMoment,
    RealtimeSharedMemoryCandidate,
    RealtimeMemoryExpiryEvent,
)
from app.db.models.resident_presence import (
    CompanionResidentStatusEvent,
    CompanionPresenceBudget,
    CoPresenceInvitation,
    QuietHourSetting,
    FocusModeEvent,
    ResidentPresenceEvent,
    ScopedHardStopEvent,
    HardStopAuditEvent,
)
from app.db.models.realtime_trace import (
    RealtimeTraceSession,
    RealtimeTraceEvent,
    ParticipantEventTrace,
    SpeakerTrace,
    PermissionAuditEvent,
    MemoryGateTrace,
    RealtimeReplay,
    RealtimeReplaySegment,
    RedactionEvent,
)
from app.db.models.channel_gateway_readiness import (
    PresenceChannelBinding,
    CompanionChannelIdentity,
    ChannelPermissionPolicy,
    ChannelMessageEvent,
    ChannelMemoryBoundaryPolicy,
    ChannelAuditEvent,
    ChannelRevokeEvent,
)
from app.db.models.channel_gateway import (
    ChannelProvider,
    ChannelProviderConfig,
    ChannelBotRegistry,
    ChannelBinding,
    ChannelWebhookEvent,
    ChannelDeliveryEvent,
    ChannelRateLimitEvent,
    ChannelFailureEvent,
    DiscordDmConversationBinding,
    DiscordDmDelivery,
    ChannelEphemeralBuffer,
    ChannelEphemeralBufferItem,
    ChannelMemoryCandidate,
    ChannelMemoryReview,
    ChannelContextRedactionEvent,
    ChannelPresencePolicy,
    ChannelCheckinSetting,
    ChannelPresenceBudgetEvent,
    ChannelQuietHourRule,
    ChannelFocusModeRule,
    ChannelMeaningfulSilenceEvent,
    ChannelOutboundSuppressionEvent,
    ChannelTraceEvent,
    ChannelAuditLog,
    ChannelBindingStatusEvent,
    ChannelOutboundAuditEvent,
    ChannelMemoryGateTrace,
)

__all__ = [
    # Core conversation
    "User",
    "Companion",
    "CompanionMode",
    "CompanionDeletionRequest",
    "CompanionDeletionScopeRow",
    "ConversationDeletionProof",
    "Conversation",
    "Message",
    "Memory",
    "MemoryCandidate",
    "MemoryEdge",
    "GrowthCandidate",
    "GrowthRecord",
    "RelationshipState",
    "RelationshipEvent",
    "RelationshipCandidate",
    "CompanionChronicleSummary",
    "RelationshipStateRevision",
    "CompanionAffectState",
    "CompanionAffectEvent",
    "PresenceOpportunity",
    "PresenceSchedule",
    "PresenceScheduleOccurrence",
    "BoundarySetting",
    "TraceRun",
    "TraceStep",
    "ProjectContext",
    "CreativeContext",
    "BadCase",
    # Continuity
    "FeedbackEvent",
    "MemoryUsageEvent",
    "MemoryLifecycleEvent",
    "MemoryAbstractionCandidate",
    "ContinuitySnapshot",
    "UserStateSnapshot",
    "RelationshipExplanationEvent",
    "ReviewBatch",
    # Agent execution
    "ToolDefinition",
    "ToolPermission",
    "ToolRun",
    "ToolRunStep",
    "ToolRunArtifact",
    "ToolResource",
    "FileSource",
    "FileDocument",
    "FileChunk",
    "FileContextUsage",
    "ProjectMilestone",
    "ProjectTask",
    "ProjectTaskEvent",
    "ProjectTaskEvidenceLink",
    "ConversationTaskRun",
    "ConversationTaskStep",
    "ConversationTaskStepAttempt",
    "ConversationTaskPlanRevision",
    "AgentRunReplay",
    "TraceReplaySession",
    "ReplayAnnotation",
    "BadCaseInboxItem",
    "BadCaseLink",
    "BadCaseTriageEvent",
    "BadCaseCluster",
    "EvaluationDataset",
    "EvaluationCase",
    "EvaluationRun",
    "EvaluationResult",
    "EvaluationMetric",
    "RegressionCase",
    "RegressionRun",
    "RegressionResult",
    "LlmProviderConfig",
    "LlmModelConfig",
    "PromptVersion",
    "LlmCallRecord",
    "FallbackEvent",
    "RerankerTrainingExample",
    "MemoryRerankerRun",
    "PresencePolicyFeedbackSample",
    "PresencePolicyRun",
    "EvidenceSufficiencyEvent",
    "GrowthConsistencyCheck",
    "OutdatedMemoryFlag",
    "OutdatedMemoryReview",
    # Companion
    "CompanionIdentityProfile",
    "CompanionPersonaProfile",
    "CompanionRelationshipContract",
    "CompanionBoundaryProfile",
    "CompanionVisibilityPolicy",
    "CompanionLifecycleEvent",
    "CompanionMemoryScope",
    "CompanionPrivateMemoryLink",
    "RelationshipMemoryLink",
    "SharedEpisodicMemory",
    "SharedMemoryCandidate",
    "SharedMemoryParticipant",
    "CrossCompanionMemoryEvent",
    "CrossCompanionMemoryReview",
    "PrivateToSharedMemoryReview",
    "SharedToPrivateMemoryReview",
    "CoPresenceSession",
    "CoPresenceParticipant",
    "CoPresenceSessionPolicy",
    "CompanionRoomTurn",
    "CompanionRoomTurnStep",
    "ParticipantAwarenessState",
    "ParticipantMemoryPermission",
    "SharedScene",
    "SharedSceneEvent",
    "SharedExperienceRecord",
    "CompanionPersonaGrowthCandidate",
    "CompanionPersonaGrowthEvent",
    "CompanionPersonaDriftCheck",
    "GroupPersonaConsistencyCheck",
    "MutualPresencePolicyRun",
    "CompanionPresenceOpportunity",
    "CoPresenceOpportunity",
    "CompanionPresenceFeedbackEvent",
    # Realtime compatibility
    "RealtimeCoPresenceSession",
    "RealtimeCoPresenceParticipant",
    "RealtimeParticipantState",
    "RealtimeSessionChannel",
    "RealtimeSessionStateEvent",
    "RealtimeChannelStateEvent",
    "VoiceProviderConfig",
    "CompanionVoiceProfile",
    "CompanionVoiceSession",
    "VoiceTurn",
    "SttEvent",
    "TtsEvent",
    "TurnTakingEvent",
    "VoiceInterruptionEvent",
    "VoicePersonaGuardRun",
    "MultimodalContextEvent",
    "ImageContextEvent",
    "ScreenContextEvent",
    "FileContextRealtimeEvent",
    "DeviceContextEvent",
    "ParticipantContextPermission",
    "ContextRetentionPolicy",
    "EphemeralContextExpiryEvent",
    "RealtimeMemoryBuffer",
    "RealtimeMemoryBufferItem",
    "CompanionPrivateRealtimeBuffer",
    "CoPresenceSessionBuffer",
    "SharedSceneBuffer",
    "SalientMoment",
    "CompanionPrivateSalientMoment",
    "SharedSalientMoment",
    "RealtimeSharedMemoryCandidate",
    "RealtimeMemoryExpiryEvent",
    "CompanionResidentStatusEvent",
    "CompanionPresenceBudget",
    "CoPresenceInvitation",
    "QuietHourSetting",
    "FocusModeEvent",
    "ResidentPresenceEvent",
    "ScopedHardStopEvent",
    "HardStopAuditEvent",
    "RealtimeTraceSession",
    "RealtimeTraceEvent",
    "ParticipantEventTrace",
    "SpeakerTrace",
    "PermissionAuditEvent",
    "MemoryGateTrace",
    "RealtimeReplay",
    "RealtimeReplaySegment",
    "RedactionEvent",
    "PresenceChannelBinding",
    "CompanionChannelIdentity",
    "ChannelPermissionPolicy",
    "ChannelMessageEvent",
    "ChannelMemoryBoundaryPolicy",
    "ChannelAuditEvent",
    "ChannelRevokeEvent",
    # Channel Gateway
    "ChannelProvider",
    "ChannelProviderConfig",
    "ChannelBotRegistry",
    "ChannelBinding",
    "ChannelWebhookEvent",
    "ChannelDeliveryEvent",
    "ChannelRateLimitEvent",
    "ChannelFailureEvent",
    "DiscordDmConversationBinding",
    "DiscordDmDelivery",
    "ChannelEphemeralBuffer",
    "ChannelEphemeralBufferItem",
    "ChannelMemoryCandidate",
    "ChannelMemoryReview",
    "ChannelContextRedactionEvent",
    "ChannelPresencePolicy",
    "ChannelCheckinSetting",
    "ChannelPresenceBudgetEvent",
    "ChannelQuietHourRule",
    "ChannelFocusModeRule",
    "ChannelMeaningfulSilenceEvent",
    "ChannelOutboundSuppressionEvent",
    "ChannelTraceEvent",
    "ChannelAuditLog",
    "ChannelBindingStatusEvent",
    "ChannelOutboundAuditEvent",
    "ChannelMemoryGateTrace",
]
