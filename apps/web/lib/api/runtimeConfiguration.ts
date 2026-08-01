import { ApiError, request } from "./client";

export interface SecretStatus {
  configured: boolean;
  source: "local_protected" | "environment" | "missing";
  updated_at: string | null;
  last_four: null;
}

export interface DiscordRuntimeBot {
  bot_key: string;
  display_name?: string;
  enabled?: boolean;
  app_id?: string;
  application_id?: string;
  public_key?: string;
  oauth2_url?: string;
  guild_id?: string;
  default_channel_id?: string;
  companion_id?: string;
  token: SecretStatus;
  client_secret: SecretStatus;
}

export interface ConnectionVerification {
  status: string;
  status_code?: number | null;
  real_provider_call: boolean;
  probe_scope: "database_and_migrations" | "endpoint_and_credential_only" | "discord_bot_identity" | "unknown";
  selected_capability_validated: false;
  migration_status?: "current" | "outdated" | "uninitialized" | "unknown";
  tested_at: string;
  configuration_revision: number | null;
}

export interface RuntimeConfiguration {
  contract_version: "runtime-configuration.v1";
  revision: number;
  security_mode: string;
  database: {
    connection: SecretStatus;
    effective_source: string;
    reload_mode: string;
  };
  llm: {
    provider: string;
    base_url: string;
    model: string;
    model_fallbacks: string[];
    api_key: SecretStatus;
    effective_source: string;
    reload_mode: string;
  };
  embedding: {
    provider: string;
    base_url: string;
    model: string;
    model_fallbacks: string[];
    dimensions: number;
    api_key: SecretStatus;
    effective_source: string;
    reload_mode: string;
  };
  discord: {
    bots: DiscordRuntimeBot[];
    file_registry_detected: boolean;
    reload_mode: string;
  };
  verification: {
    database: ConnectionVerification | null;
    llm: ConnectionVerification | null;
    embedding: ConnectionVerification | null;
    discord: Record<string, ConnectionVerification>;
  };
  secret_values_returned: false;
}

interface ControlSession {
  session_token: string;
  csrf_token: string;
  expires_at: string;
}

let controlSession: ControlSession | null = null;
let sessionPromise: Promise<ControlSession> | null = null;

async function ensureSession(): Promise<ControlSession> {
  if (controlSession && Date.parse(controlSession.expires_at) > Date.now() + 5_000) return controlSession;
  if (!sessionPromise) {
    sessionPromise = request<ControlSession>("/runtime-configuration/session", { method: "POST", body: "{}" })
      .then((value) => {
        controlSession = value;
        return value;
      })
      .finally(() => {
        sessionPromise = null;
      });
  }
  return sessionPromise;
}

async function secureRequest<T>(path: string, options?: RequestInit, retry = true): Promise<T> {
  const session = await ensureSession();
  const headers = new Headers(options?.headers);
  headers.set("X-Echora-Config-Session", session.session_token);
  headers.set("X-Echora-CSRF", session.csrf_token);
  try {
    return await request<T>(path, {
      ...options,
      headers,
    });
  } catch (error) {
    if (retry && error instanceof ApiError && error.code === "LOCAL_CONFIGURATION_SESSION_INVALID") {
      controlSession = null;
      return secureRequest<T>(path, options, false);
    }
    throw error;
  }
}

export function getRuntimeConfiguration() {
  return secureRequest<RuntimeConfiguration>("/runtime-configuration");
}

export interface RuntimeConfigurationUpdate {
  expected_revision: number;
  llm: Partial<RuntimeConfiguration["llm"]>;
  embedding: Partial<RuntimeConfiguration["embedding"]>;
  discord: { bots: Array<Omit<DiscordRuntimeBot, "token" | "client_secret">> };
  secret_replacements: {
    database_url?: string;
    llm_api_key?: string;
    embedding_api_key?: string;
    discord_bot_tokens?: Record<string, string>;
    discord_client_secrets?: Record<string, string>;
  };
  secret_removals?: {
    database_url?: true;
    llm_api_key?: true;
    embedding_api_key?: true;
    discord_bot_tokens?: string[];
    discord_client_secrets?: string[];
  };
}

export function updateRuntimeConfiguration(data: RuntimeConfigurationUpdate) {
  return secureRequest<RuntimeConfiguration>("/runtime-configuration", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function testRuntimeConfiguration(target: "database" | "llm" | "embedding" | "discord", botKey?: string) {
  return secureRequest<ConnectionVerification & { target: string }>(
    "/runtime-configuration/test",
    { method: "POST", body: JSON.stringify({ target, bot_key: botKey }) },
  );
}
