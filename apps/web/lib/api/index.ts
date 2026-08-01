/** Echora API client — barrel export. */

export { api, ApiError } from "./client";
export type { ApiResponse } from "./client";

export * as companionApi from "./companions";
export * as companionIdentityApi from "./companionIdentity";
export * as companionMemoryApi from "./companionMemory";
export * as conversationApi from "./conversations";
export * as toolApi from "./tools";
export * as fileApi from "./files";
export * as projectApi from "./projects";
export * as replayApi from "./replays";
export * as badCaseInboxApi from "./badCaseInbox";
export * as evaluationApi from "./evaluation";
export * as regressionApi from "./regression";
export * as providerApi from "./providers";
export * as strategyApi from "./strategy";
export * as evidenceApi from "./evidence";
export * as sharedMemoryApi from "./sharedMemory";
export * as coPresenceApi from "./coPresence";
export * as sharedScenesApi from "./sharedScenes";
export * as personaGrowthApi from "./personaGrowth";
export * as mutualPresenceApi from "./mutualPresence";
export * as delegatedExecutionApi from "./delegatedExecution";
export * as realtimeCoPresenceApi from "./realtimeCoPresence";
export * as realtimeChannelApi from "./realtimeChannel";
export * as companionVoiceApi from "./companionVoice";
export * as multimodalContextApi from "./multimodalContext";
export * as realtimeMemoryApi from "./realtimeMemory";
export * as residentPresenceApi from "./residentPresence";
export * as hardStopApi from "./hardStop";
export * as realtimeTraceApi from "./realtimeTrace";
export * as channelGatewayApi from "./channelGateway";
