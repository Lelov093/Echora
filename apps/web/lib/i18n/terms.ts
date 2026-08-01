export const terms = {
  companionConstellation: "伙伴星图",
  companionRoom: "伙伴空间",
  conversation: "对话",
  livingChronicle: "共同历程",
  reviewInbox: "审核收件箱",
  presence: "在场感",
  memoryCandidate: "待确认记忆",
  growthCandidate: "待确认成长",
  trace: "回应依据",
  boundary: "边界与权限",
  sharedScene: "共享场景",
  studio: "Studio / 高级工作区",
} as const;

export type TermKey = keyof typeof terms;
