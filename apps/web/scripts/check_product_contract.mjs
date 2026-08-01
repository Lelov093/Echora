import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

const diagnostics = read("features/system/SystemWorkspace.tsx");
const conversation = read("features/conversation/ConversationWorkspace.tsx");
const conversationEvidence = read("../../services/agent-api/app/services/conversation_evidence_service.py");
const legacyDiagnosticsRoute = read("app/diagnostics/page.tsx");
const webReadme = read("README.md");
const realtimeRoute = read("app/realtime/page.tsx");
const voiceRoute = read("app/realtime/voice/page.tsx");
const channelAuditRoute = read("app/settings/channels/audit/page.tsx");

assert.match(legacyDiagnosticsRoute, /redirect\("\/settings\/system\/diagnostics"\)/);
assert.match(diagnostics, /getRuntimeConfiguration/);
assert.match(diagnostics, /当前需要关注/);
assert.match(diagnostics, /高级诊断信息/);
assert.match(diagnostics, /href="\/settings\/system\/shadow-policies"/);
assert.match(diagnostics, /策略运行证据/);
assert.match(conversation, /本轮上下文/);
assert.match(conversation, /本轮活动/);
assert.match(conversation, /本对话待确认/);
assert.match(conversation, /所选伙伴回复/);
assert.doesNotMatch(conversation, /className="conversation-context-button"/);
assert.match(conversation, /onOpenPanel\(message\.id, "context"\)/);
assert.match(conversation, /onOpenPanel\(message\.id, "task"\)/);
assert.match(conversationEvidence, /row\.status == "skipped"/);
assert.match(conversationEvidence, /"reason": None/);
assert.match(conversationEvidence, /conversation-response-process\.v1/);
assert.match(conversationEvidence, /"title": "理解你的消息"/);
assert.match(conversation, /查看这次回应的过程/);
assert.doesNotMatch(conversation, /执行受控步骤|trace\.data\.steps|getTrace/);
assert.doesNotMatch(diagnostics, /未实现能力准确状态/);
assert.doesNotMatch(diagnostics, /内部可靠性批次/);
assert.doesNotMatch(diagnostics, />Activation gate/);
assert.doesNotMatch(diagnostics, />Shadow only/);
assert.doesNotMatch(webReadme, /create-next-app|Deploy on Vercel|Geist/);
assert.match(realtimeRoute, /redirect\("\/presence"\)/);
assert.match(voiceRoute, /redirect\("\/presence"\)/);
assert.match(channelAuditRoute, /redirect\("\/settings\/channels\/discord"\)/);

console.log("Echora product contract check passed (27 assertions).");
