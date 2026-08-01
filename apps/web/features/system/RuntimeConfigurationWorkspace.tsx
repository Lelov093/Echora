"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, BrainCircuit, Database, Plus, ServerCog, Trash2 } from "lucide-react";
import {
  SettingsAction,
  SettingsActionBar,
  SettingsField,
  SettingsInlineNotice,
  SettingsSectionHeading,
  SettingsStateSwitch,
  SettingsStatusPill,
} from "@/components/settings/SettingsControls";
import { DataState } from "@/components/patterns/DataState";
import { ApiError } from "@/lib/api/client";
import {
  getRuntimeConfiguration,
  testRuntimeConfiguration,
  updateRuntimeConfiguration,
  type ConnectionVerification,
  type DiscordRuntimeBot,
  type RuntimeConfiguration,
  type RuntimeConfigurationUpdate,
} from "@/lib/api/runtimeConfiguration";

const queryKey = ["runtime-configuration", "v1"] as const;
type SafeBot = Omit<DiscordRuntimeBot, "token" | "client_secret">;

function configurationErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : "安全配置操作失败。";
  const messages: Record<string, string> = {
    LOCAL_CONFIGURATION_LOOPBACK_REQUIRED: "安全配置只能从当前设备访问。",
    LOCAL_CONFIGURATION_ORIGIN_REJECTED: "当前页面来源不允许访问安全配置。",
    LOCAL_CONFIGURATION_SESSION_INVALID: "安全配置会话已过期，请刷新后重试。",
    RUNTIME_CONFIGURATION_REVISION_CONFLICT: "配置已在其他页面发生变化，请刷新后重新编辑。",
    RUNTIME_CONFIGURATION_REVISION_INVALID: "配置版本无效，请刷新页面。",
    RUNTIME_CONFIGURATION_PROVIDER_INVALID: "所选 Provider 当前不受支持。",
    RUNTIME_CONFIGURATION_BASE_URL_INVALID: "Base URL 必须是有效的 HTTP 或 HTTPS 地址。",
    RUNTIME_CONFIGURATION_DATABASE_URL_INVALID: "数据库连接必须使用 postgresql+psycopg，并包含主机、数据库名和用户名。",
    RUNTIME_CONFIGURATION_FIELD_TOO_LONG: "配置字段超过允许长度。",
    RUNTIME_CONFIGURATION_MODEL_FALLBACKS_INVALID: "备用模型配置无效。",
    EMBEDDING_DIMENSION_CHANGE_REQUIRES_SEPARATE_APPROVAL: "Embedding 维度变化需要单独批准 reindex。",
    DISCORD_BOT_COUNT_INVALID: "Discord Bot 数量超过当前上限。",
    DISCORD_BOT_KEY_INVALID: "每个 Discord Bot 都需要唯一且格式有效的 Bot key。",
    DISCORD_SNOWFLAKE_INVALID: "Discord App、Guild 或 Channel ID 必须是有效的数字 Snowflake。",
    DISCORD_PUBLIC_KEY_INVALID: "Discord Public Key 必须是 64 位十六进制字符。",
    DISCORD_OAUTH_URL_INVALID: "OAuth2 URL 必须使用 Discord 官方 HTTPS 地址。",
    RUNTIME_CONFIGURATION_SECRET_FIELD_INVALID: "凭据替换包含不受支持的字段。",
    RUNTIME_CONFIGURATION_SECRET_INVALID: "凭据为空、过长或格式无效。",
    RUNTIME_CONFIGURATION_ATOMIC_WRITE_FAILED: "配置未能安全写入，最后可用版本保持不变。",
  };
  return messages[error.code] ?? error.message;
}

function withoutToken(bot: DiscordRuntimeBot): SafeBot {
  const safe = { ...bot } as Partial<DiscordRuntimeBot>;
  delete safe.token;
  delete safe.client_secret;
  return safe as SafeBot;
}

function connectionLabel(status: string) {
  return {
    connected: "端点与凭据可用",
    rejected: "凭据或权限被拒绝",
    unreachable: "服务不可达",
    not_configured: "配置不完整",
  }[status] ?? status;
}

function migrationLabel(status?: ConnectionVerification["migration_status"]) {
  return {
    current: "Migration 已是最新",
    outdated: "Migration 需要升级",
    uninitialized: "数据库尚未初始化",
    unknown: "Migration 状态未知",
  }[status || "unknown"];
}

function connectionTone(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "connected") return "success";
  if (status === "not_configured") return "warning";
  if (status === "rejected" || status === "unreachable") return "danger";
  return "info";
}

function ConnectionState({
  evidence,
  error,
  blocked,
  emptyText = "尚未测试",
}: {
  evidence?: ConnectionVerification | null;
  error?: string;
  blocked?: boolean;
  emptyText?: string;
}) {
  if (blocked) return <span className="runtime-connection-note">请先保存当前配置，再测试实际生效值。</span>;
  if (error) {
    return <span className="runtime-connection-state"><SettingsStatusPill tone="danger">测试请求失败</SettingsStatusPill><small>{error}</small></span>;
  }
  if (!evidence) return <span className="runtime-connection-note">{emptyText}</span>;
  return (
    <span className="runtime-connection-state">
      <SettingsStatusPill tone={connectionTone(evidence.status)}>{connectionLabel(evidence.status)}</SettingsStatusPill>
      <small>
        {new Date(evidence.tested_at).toLocaleString("zh-CN")} · 配置版本 {evidence.configuration_revision ?? "—"}
        {" · "}{
          evidence.probe_scope === "database_and_migrations"
            ? migrationLabel(evidence.migration_status)
            : evidence.probe_scope === "discord_bot_identity"
              ? "已验证 Bot identity，未验证 Guild/Channel"
              : "未执行所选模型生成"
        }
      </small>
    </span>
  );
}

function credentialLabel(secret: RuntimeConfiguration["llm"]["api_key"]) {
  if (!secret.configured) return "缺少凭据";
  const source = secret.source === "local_protected" ? "受保护本地凭据" : "环境变量";
  if (!secret.updated_at) return source;
  return `${source} · ${new Date(secret.updated_at).toLocaleString("zh-CN")}`;
}

export function RuntimeConfigurationWorkspace() {
  const query = useQuery({ queryKey, queryFn: getRuntimeConfiguration, staleTime: 10_000 });
  if (query.isPending) {
    return <DataState kind="loading" title="正在建立受信配置会话" description="只允许当前设备与受信 Web Origin 访问。" />;
  }
  if (query.isError || !query.data) {
    return (
      <DataState
        kind="error"
        title="安全配置中心暂不可用"
        description={configurationErrorMessage(query.error)}
      />
    );
  }
  return <RuntimeConfigurationEditor key={query.data.revision} configuration={query.data} />;
}

function RuntimeConfigurationEditor({ configuration }: { configuration: RuntimeConfiguration }) {
  const queryClient = useQueryClient();
  const [llm, setLlm] = useState(() => ({
    provider: configuration.llm.provider,
    base_url: configuration.llm.base_url,
    model: configuration.llm.model,
    model_fallbacks: configuration.llm.model_fallbacks.join(", "),
  }));
  const [databaseUrl, setDatabaseUrl] = useState("");
  const [embedding, setEmbedding] = useState(() => ({
    provider: configuration.embedding.provider,
    base_url: configuration.embedding.base_url,
    model: configuration.embedding.model,
    model_fallbacks: configuration.embedding.model_fallbacks.join(", "),
    dimensions: configuration.embedding.dimensions,
  }));
  const [bots, setBots] = useState<SafeBot[]>(() => configuration.discord.bots.map(withoutToken));
  const [llmKey, setLlmKey] = useState("");
  const [embeddingKey, setEmbeddingKey] = useState("");
  const [discordTokens, setDiscordTokens] = useState<Record<string, string>>({});
  const [discordClientSecrets, setDiscordClientSecrets] = useState<Record<string, string>>({});
  const [secretRemovals, setSecretRemovals] = useState<Set<string>>(() => new Set());
  const [testState, setTestState] = useState<Record<string, ConnectionVerification>>(() => ({
    ...(configuration.verification.database ? { database: configuration.verification.database } : {}),
    ...(configuration.verification.llm ? { llm: configuration.verification.llm } : {}),
    ...(configuration.verification.embedding ? { embedding: configuration.verification.embedding } : {}),
    ...Object.fromEntries(
      Object.entries(configuration.verification.discord).map(([botKey, evidence]) => [`discord:${botKey}`, evidence]),
    ),
  }));
  const [testErrors, setTestErrors] = useState<Record<string, string>>({});
  const [confirmingSecretReplacement, setConfirmingSecretReplacement] = useState(false);

  const save = useMutation({
    mutationFn: (payload: RuntimeConfigurationUpdate) => updateRuntimeConfiguration(payload),
    onSuccess: (value) => queryClient.setQueryData(queryKey, value),
  });
  const test = useMutation({
    mutationFn: ({ target, botKey }: { target: "database" | "llm" | "embedding" | "discord"; botKey?: string }) =>
      testRuntimeConfiguration(target, botKey),
    onMutate: (variables) => {
      const key = variables.botKey ? `discord:${variables.botKey}` : variables.target;
      setTestErrors((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
    },
    onSuccess: (value, variables) => {
      const key = variables.botKey ? `discord:${variables.botKey}` : variables.target;
      setTestState((current) => ({ ...current, [key]: value }));
    },
    onError: (error, variables) => {
      const key = variables.botKey ? `discord:${variables.botKey}` : variables.target;
      setTestErrors((current) => ({
        ...current,
        [key]: configurationErrorMessage(error),
      }));
    },
  });

  const originalBots = configuration.discord.bots.map(withoutToken);
  const databaseDirty = Boolean(databaseUrl);
  const llmDirty =
    llm.provider !== configuration.llm.provider ||
    llm.base_url !== configuration.llm.base_url ||
    llm.model !== configuration.llm.model ||
    llm.model_fallbacks !== configuration.llm.model_fallbacks.join(", ") ||
    Boolean(llmKey);
  const embeddingDirty =
    embedding.provider !== configuration.embedding.provider ||
    embedding.base_url !== configuration.embedding.base_url ||
    embedding.model !== configuration.embedding.model ||
    embedding.model_fallbacks !== configuration.embedding.model_fallbacks.join(", ") ||
    Boolean(embeddingKey);
  const discordDirty =
    JSON.stringify(bots) !== JSON.stringify(originalBots) ||
    Object.values(discordTokens).some(Boolean) ||
    Object.values(discordClientSecrets).some(Boolean);
  const dirty = databaseDirty || llmDirty || embeddingDirty || discordDirty || secretRemovals.size > 0;
  const hasSecretChange = Boolean(
    databaseUrl ||
    llmKey ||
    embeddingKey ||
    Object.values(discordTokens).some((token) => token.trim()) ||
    Object.values(discordClientSecrets).some((secret) => secret.trim()) ||
    secretRemovals.size > 0,
  );
  const activeTestKey = test.variables?.botKey ? `discord:${test.variables.botKey}` : test.variables?.target;

  function addBot() {
    let suffix = bots.length + 1;
    while (bots.some((bot) => bot.bot_key === `discord-${suffix}`)) suffix += 1;
    setBots((current) => [
      ...current,
      { bot_key: `discord-${suffix}`, display_name: "新的 Discord Bot", enabled: true },
    ]);
  }

  function updateBot(index: number, patch: Partial<SafeBot>) {
    setBots((current) => current.map((bot, botIndex) => (botIndex === index ? { ...bot, ...patch } : bot)));
  }

  function toggleSecretRemoval(key: string) {
    setSecretRemovals((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function keepSecret(key: string) {
    setSecretRemovals((current) => {
      if (!current.has(key)) return current;
      const next = new Set(current);
      next.delete(key);
      return next;
    });
  }

  function renameBot(index: number, nextKey: string) {
    const previousKey = bots[index]?.bot_key;
    updateBot(index, { bot_key: nextKey });
    if (!previousKey || previousKey === nextKey) return;
    setDiscordTokens((current) => {
      if (!current[previousKey]) return current;
      const next = { ...current, [nextKey]: current[previousKey] };
      delete next[previousKey];
      return next;
    });
  }

  function generateDiscordOAuthUrl(index: number) {
    const applicationId = bots[index]?.app_id || bots[index]?.application_id;
    if (!applicationId) return;
    updateBot(index, {
      oauth2_url: `https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(applicationId)}&scope=bot%20applications.commands`,
    });
  }

  function submit() {
    save.mutate({
      expected_revision: configuration.revision,
      llm: {
        ...llm,
        model_fallbacks: llm.model_fallbacks.split(",").map((item) => item.trim()).filter(Boolean),
      },
      embedding: {
        ...embedding,
        model_fallbacks: embedding.model_fallbacks.split(",").map((item) => item.trim()).filter(Boolean),
      },
      discord: { bots },
      secret_replacements: {
        ...(databaseUrl ? { database_url: databaseUrl } : {}),
        ...(llmKey ? { llm_api_key: llmKey } : {}),
        ...(embeddingKey ? { embedding_api_key: embeddingKey } : {}),
        discord_bot_tokens: Object.fromEntries(
          Object.entries(discordTokens).filter(([, token]) => token.trim()),
        ),
        discord_client_secrets: Object.fromEntries(
          Object.entries(discordClientSecrets).filter(([, secret]) => secret.trim()),
        ),
      },
      secret_removals: {
        ...(secretRemovals.has("database_url") ? { database_url: true as const } : {}),
        ...(secretRemovals.has("llm_api_key") ? { llm_api_key: true as const } : {}),
        ...(secretRemovals.has("embedding_api_key") ? { embedding_api_key: true as const } : {}),
        discord_bot_tokens: [...secretRemovals]
          .filter((key) => key.startsWith("discord-token:"))
          .map((key) => key.slice("discord-token:".length)),
        discord_client_secrets: [...secretRemovals]
          .filter((key) => key.startsWith("discord-client-secret:"))
          .map((key) => key.slice("discord-client-secret:".length)),
      },
    });
  }

  return (
    <div className="runtime-config-workspace">
      <SettingsInlineNotice tone="success">
        <strong>受信本地控制面</strong>
        <span>Loopback、Origin、短期 Session 与 CSRF 均需通过验证；密钥仅可替换，已存 Secret 永不回显。</span>
      </SettingsInlineNotice>
      <section className="runtime-readiness" aria-label="首次使用顺序">
        <strong>开始第一段真实对话</strong>
        <ol>
          <li className={configuration.verification.database?.status === "connected" && configuration.verification.database?.migration_status === "current" ? "is-ready" : ""}>连接并初始化数据库</li>
          <li className={configuration.llm.api_key.configured && Boolean(configuration.llm.model) ? "is-ready" : ""}>配置对话模型</li>
          <li className={configuration.embedding.api_key.configured && Boolean(configuration.embedding.model) ? "is-ready" : ""}>配置记忆向量模型</li>
          <li>创建伙伴并开始 Conversation</li>
        </ol>
        <p>Discord 是可选渠道，可以在核心对话可用后再配置。</p>
      </section>
      {save.isError ? (
        <SettingsInlineNotice tone="danger">
          {configurationErrorMessage(save.error)}
        </SettingsInlineNotice>
      ) : null}

      <section className="runtime-config-section" aria-labelledby="runtime-database-title">
        <SettingsSectionHeading
          id="runtime-database-title"
          icon={Database}
          eyebrow="DATABASE"
          title="长期记忆数据库"
          description="连接 URL 以 write-only Secret 保存。保存后重启 Agent API 才会切换连接；数据库不可用时，本页仍作为恢复入口。"
          action={
            <SettingsStatusPill tone={configuration.database.connection.configured ? "success" : "warning"}>
              {credentialLabel(configuration.database.connection)}
            </SettingsStatusPill>
          }
        />
        <div className="runtime-config-grid">
          <SettingsField
            className="is-wide"
            label="替换 PostgreSQL 连接 URL"
            description="留空保留当前连接；URL 中的密码不会回显。需要 PostgreSQL 与 pgvector。"
          >
            <div className="runtime-secret-field">
              <input
                type="password"
                value={databaseUrl}
                onChange={(event) => { setDatabaseUrl(event.target.value); keepSecret("database_url"); }}
                autoComplete="new-password"
                placeholder="postgresql+psycopg://user:password@127.0.0.1:5432/echora"
                maxLength={8192}
              />
              {configuration.database.connection.source === "local_protected" ? <SettingsAction variant="quiet" onClick={() => toggleSecretRemoval("database_url")}>{secretRemovals.has("database_url") ? "保留原值" : "清除本地连接"}</SettingsAction> : null}
            </div>
          </SettingsField>
        </div>
        <div className="runtime-config-actions">
          <SettingsAction onClick={() => test.mutate({ target: "database" })} busy={test.isPending && activeTestKey === "database"} disabled={databaseDirty}>测试数据库与 Migration</SettingsAction>
          <ConnectionState evidence={testState.database} error={testErrors.database} blocked={databaseDirty} />
        </div>
        <p className="runtime-config-guidance">
          首次连接后，在 <code>services/agent-api</code> 运行 <code>.\.venv\Scripts\python.exe -m alembic upgrade head</code>，再返回重新测试。
        </p>
      </section>

      <section className="runtime-config-section" aria-labelledby="runtime-llm-title">
        <SettingsSectionHeading
          id="runtime-llm-title"
          icon={BrainCircuit}
          eyebrow="LLM"
          title="对话模型"
          description="下一次 Conversation turn 读取最新配置，不需要重启 8010。"
          action={
            <SettingsStatusPill tone={configuration.llm.api_key.configured ? "success" : "warning"}>
              {credentialLabel(configuration.llm.api_key)}
            </SettingsStatusPill>
          }
        />
        <div className="runtime-config-grid">
          <SettingsField label="Provider">
            <select value={llm.provider} onChange={(event) => setLlm({ ...llm, provider: event.target.value })}>
              <option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </SettingsField>
          <SettingsField label="Model">
            <input value={llm.model} onChange={(event) => setLlm({ ...llm, model: event.target.value })} placeholder="模型名称" maxLength={256} />
          </SettingsField>
          <SettingsField className="is-wide" label="备用模型顺序" description="主模型不可用时按从左到右尝试，最多 10 个；使用英文逗号分隔。">
            <input value={llm.model_fallbacks} onChange={(event) => setLlm({ ...llm, model_fallbacks: event.target.value })} placeholder="fallback-a, fallback-b" maxLength={2560} />
          </SettingsField>
          <SettingsField className="is-wide" label="Base URL">
            <input value={llm.base_url} onChange={(event) => setLlm({ ...llm, base_url: event.target.value })} placeholder="https://…/v1" inputMode="url" maxLength={2048} />
          </SettingsField>
          <SettingsField className="is-wide" label="替换 API Key" description="留空表示保留已存 Secret；浏览器不会读取旧值。">
            <div className="runtime-secret-field">
              <input type="password" value={llmKey} onChange={(event) => { setLlmKey(event.target.value); keepSecret("llm_api_key"); }} autoComplete="new-password" placeholder="••••••••" maxLength={8192} />
              {configuration.llm.api_key.source === "local_protected" ? <SettingsAction variant="quiet" onClick={() => toggleSecretRemoval("llm_api_key")}>{secretRemovals.has("llm_api_key") ? "保留原值" : "清除本地凭据"}</SettingsAction> : null}
            </div>
          </SettingsField>
        </div>
        <div className="runtime-config-actions">
          <SettingsAction onClick={() => test.mutate({ target: "llm" })} busy={test.isPending && activeTestKey === "llm"} disabled={llmDirty}>测试连接</SettingsAction>
          <ConnectionState evidence={testState.llm} error={testErrors.llm} blocked={llmDirty} />
        </div>
      </section>

      <section className="runtime-config-section" aria-labelledby="runtime-embedding-title">
        <SettingsSectionHeading
          id="runtime-embedding-title"
          icon={ServerCog}
          eyebrow="EMBEDDING"
          title="记忆向量模型"
          description="维度保持当前 1024；改变维度仍需单独批准 reindex。"
          action={
            <SettingsStatusPill tone={configuration.embedding.api_key.configured ? "success" : "warning"}>
              {credentialLabel(configuration.embedding.api_key)}
            </SettingsStatusPill>
          }
        />
        <div className="runtime-config-grid">
          <SettingsField label="Provider">
            <select value={embedding.provider} onChange={(event) => setEmbedding({ ...embedding, provider: event.target.value })}>
              <option value="auto">Auto</option>
              <option value="openai_compatible">OpenAI-compatible</option>
              <option value="dashscope_multimodal">DashScope multimodal</option>
              <option value="volcengine_ark">Volcengine Ark</option>
            </select>
          </SettingsField>
          <SettingsField label="Dimensions">
            <input value={embedding.dimensions} readOnly aria-readonly="true" />
          </SettingsField>
          <SettingsField label="Model">
            <input value={embedding.model} onChange={(event) => setEmbedding({ ...embedding, model: event.target.value })} maxLength={256} />
          </SettingsField>
          <SettingsField label="Base URL">
            <input value={embedding.base_url} onChange={(event) => setEmbedding({ ...embedding, base_url: event.target.value })} inputMode="url" maxLength={2048} />
          </SettingsField>
          <SettingsField className="is-wide" label="备用 Embedding 模型顺序" description="仅在相同维度与兼容 Provider 下使用；英文逗号分隔。">
            <input value={embedding.model_fallbacks} onChange={(event) => setEmbedding({ ...embedding, model_fallbacks: event.target.value })} maxLength={2560} />
          </SettingsField>
          <SettingsField className="is-wide" label="替换 Embedding API Key" description="留空保留当前 Secret。">
            <div className="runtime-secret-field">
              <input type="password" value={embeddingKey} onChange={(event) => { setEmbeddingKey(event.target.value); keepSecret("embedding_api_key"); }} autoComplete="new-password" placeholder="••••••••" maxLength={8192} />
              {configuration.embedding.api_key.source === "local_protected" ? <SettingsAction variant="quiet" onClick={() => toggleSecretRemoval("embedding_api_key")}>{secretRemovals.has("embedding_api_key") ? "保留原值" : "清除本地凭据"}</SettingsAction> : null}
            </div>
          </SettingsField>
        </div>
        <div className="runtime-config-actions">
          <SettingsAction onClick={() => test.mutate({ target: "embedding" })} busy={test.isPending && activeTestKey === "embedding"} disabled={embeddingDirty}>测试连接</SettingsAction>
          <ConnectionState evidence={testState.embedding} error={testErrors.embedding} blocked={embeddingDirty} />
        </div>
      </section>

      <section className="runtime-config-section" aria-labelledby="runtime-discord-title">
        <SettingsSectionHeading
          id="runtime-discord-title"
          icon={Bot}
          eyebrow="DISCORD"
          title="Bot 与渠道运行配置"
          description="Bot/Companion binding 仍由 Discord 治理页负责；这里仅管理连接 metadata 与 write-only token。"
          action={<SettingsAction onClick={addBot}><Plus size={15} aria-hidden="true" />添加 Bot</SettingsAction>}
        />
        {configuration.discord.file_registry_detected ? (
          <SettingsInlineNotice tone="warning">
            检测到已有的文件配置。保存后受保护的运行配置会成为优先真值；原文件不会被覆盖。
          </SettingsInlineNotice>
        ) : null}
        <div className="runtime-bot-list">
          {bots.map((bot, index) => {
            const original = configuration.discord.bots.find((item) => item.bot_key === bot.bot_key);
            const testKey = `discord:${bot.bot_key}`;
            return (
              <article className="runtime-bot-editor" key={`${bot.bot_key}-${index}`}>
                <header>
                  <strong>{bot.display_name || bot.bot_key}</strong>
                  <SettingsStateSwitch checked={bot.enabled !== false} onChange={(enabled) => updateBot(index, { enabled })} />
                  <SettingsAction variant="quiet" aria-label={`移除 ${bot.display_name || bot.bot_key}`} onClick={() => setBots((current) => current.filter((_, itemIndex) => itemIndex !== index))}>
                    <Trash2 size={15} aria-hidden="true" />
                  </SettingsAction>
                </header>
                <div className="runtime-config-grid">
                  <SettingsField label="Bot key">
                    <input value={bot.bot_key} onChange={(event) => renameBot(index, event.target.value)} pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,79}" maxLength={80} />
                  </SettingsField>
                  <SettingsField label="显示名称">
                    <input value={bot.display_name || ""} onChange={(event) => updateBot(index, { display_name: event.target.value })} maxLength={120} />
                  </SettingsField>
                  <SettingsField label="App ID">
                    <input value={bot.app_id || ""} onChange={(event) => updateBot(index, { app_id: event.target.value })} inputMode="numeric" pattern="\d{15,22}" maxLength={22} />
                  </SettingsField>
                  <SettingsField label="Public Key">
                    <input value={bot.public_key || ""} onChange={(event) => updateBot(index, { public_key: event.target.value })} pattern="[0-9a-fA-F]{64}" maxLength={64} />
                  </SettingsField>
                  <SettingsField label="Guild ID">
                    <input value={bot.guild_id || ""} onChange={(event) => updateBot(index, { guild_id: event.target.value })} inputMode="numeric" pattern="\d{15,22}" maxLength={22} />
                  </SettingsField>
                  <SettingsField label="默认 Channel ID">
                    <input value={bot.default_channel_id || ""} onChange={(event) => updateBot(index, { default_channel_id: event.target.value })} inputMode="numeric" pattern="\d{15,22}" maxLength={22} />
                  </SettingsField>
                  <SettingsField className="is-wide" label="OAuth2 URL">
                    <div className="runtime-secret-field">
                      <input value={bot.oauth2_url || ""} onChange={(event) => updateBot(index, { oauth2_url: event.target.value })} inputMode="url" maxLength={2048} />
                      <SettingsAction variant="quiet" disabled={!bot.app_id && !bot.application_id} onClick={() => generateDiscordOAuthUrl(index)}>生成邀请 URL</SettingsAction>
                    </div>
                  </SettingsField>
                  <SettingsField
                    className="is-wide"
                    label="替换 Bot Token"
                    description={original?.token.configured ? `${credentialLabel(original.token)}；留空保留` : "尚未配置"}
                  >
                    <div className="runtime-secret-field">
                      <input type="password" value={discordTokens[bot.bot_key] || ""} onChange={(event) => { setDiscordTokens((current) => ({ ...current, [bot.bot_key]: event.target.value })); keepSecret(`discord-token:${bot.bot_key}`); }} autoComplete="new-password" placeholder="••••••••" maxLength={8192} />
                      {original?.token.source === "local_protected" ? <SettingsAction variant="quiet" onClick={() => toggleSecretRemoval(`discord-token:${bot.bot_key}`)}>{secretRemovals.has(`discord-token:${bot.bot_key}`) ? "保留原值" : "清除本地 Token"}</SettingsAction> : null}
                    </div>
                  </SettingsField>
                  <SettingsField
                    className="is-wide"
                    label="替换 Discord Client Secret"
                    description={original?.client_secret?.configured ? `${credentialLabel(original.client_secret)}；留空保留` : "当前 Bot invite 与 DM Gateway 不需要；仅 OAuth2 code exchange 使用"}
                  >
                    <div className="runtime-secret-field">
                      <input type="password" value={discordClientSecrets[bot.bot_key] || ""} onChange={(event) => { setDiscordClientSecrets((current) => ({ ...current, [bot.bot_key]: event.target.value })); keepSecret(`discord-client-secret:${bot.bot_key}`); }} autoComplete="new-password" placeholder="••••••••" maxLength={8192} />
                      {original?.client_secret?.source === "local_protected" ? <SettingsAction variant="quiet" onClick={() => toggleSecretRemoval(`discord-client-secret:${bot.bot_key}`)}>{secretRemovals.has(`discord-client-secret:${bot.bot_key}`) ? "保留原值" : "清除本地 Secret"}</SettingsAction> : null}
                    </div>
                  </SettingsField>
                </div>
                <div className="runtime-config-actions">
                  <SettingsAction onClick={() => test.mutate({ target: "discord", botKey: bot.bot_key })} busy={test.isPending && activeTestKey === testKey} disabled={discordDirty}>测试 Bot</SettingsAction>
                  <ConnectionState evidence={testState[testKey]} error={testErrors[testKey]} blocked={discordDirty} emptyText="尚未测试该 Bot" />
                </div>
              </article>
            );
          })}
          {!bots.length ? (
            <p className="runtime-config-empty">尚未配置 Discord Bot。添加后仍需在 Discord 页面完成 Companion binding。</p>
          ) : null}
        </div>
      </section>

      <SettingsActionBar
        summary={
          confirmingSecretReplacement
            ? "确认受保护凭据变更"
            : dirty
              ? "有尚未保存的安全配置"
              : `配置版本 ${configuration.revision}`
        }
        meta={
          confirmingSecretReplacement
            ? "留空且未标记清除的 Secret 不会变化；新值保存后不会再次回显。"
            : "错误配置不会覆盖最后已知可用版本"
        }
        dirty={dirty}
      >
        {confirmingSecretReplacement ? (
          <>
            <SettingsAction onClick={() => setConfirmingSecretReplacement(false)} disabled={save.isPending}>返回检查</SettingsAction>
            <SettingsAction variant="primary" onClick={submit} busy={save.isPending}>确认变更并保存</SettingsAction>
          </>
        ) : (
          <SettingsAction
            variant="primary"
            onClick={() => hasSecretChange ? setConfirmingSecretReplacement(true) : submit()}
            busy={save.isPending}
            disabled={!dirty}
          >
            {hasSecretChange ? "检查凭据变更" : "原子保存配置"}
          </SettingsAction>
        )}
      </SettingsActionBar>
    </div>
  );
}
