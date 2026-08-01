"""Channel Gateway.1 Discord Gateway WebSocket Runtime Client.

Manages per-bot WebSocket connections to Discord Gateway API v10.
Each bot_key gets its own connection with independent heartbeat/reconnect.
Never logs or prints raw bot tokens.
"""

import asyncio
import json
import logging
import time
from typing import Any

import httpx
import websockets
import websockets.exceptions
from websockets.asyncio.client import ClientConnection

from app.services.discord_multi_bot_adapter_service import _load_registry, _resolve_token

logger = logging.getLogger(__name__)

# Shared cache: role_id → bot_key  (populated after READY + guild roles fetch)
_BOT_ROLE_CACHE: dict[str, str] = {}

DISCORD_API_VERSION = "10"
DISCORD_GATEWAY_URL = f"wss://gateway.discord.gg/?v={DISCORD_API_VERSION}&encoding=json"
DISCORD_HTTP_BASE = f"https://discord.com/api/v{DISCORD_API_VERSION}"

# Intents: GUILDS | GUILD_MESSAGES | DIRECT_MESSAGES | MESSAGE_CONTENT.
# DIRECT_MESSAGES is required for Discord DM persistent DM continuity.
DEFAULT_INTENTS = (1 << 0) | (1 << 9) | (1 << 12) | (1 << 15)

HEARTBEAT_TIMEOUT = 60.0
RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY = 120.0


class DiscordGatewayBot:
    """Single bot WebSocket connection to Discord Gateway."""

    def __init__(self, bot_key: str, bot_meta: dict[str, Any], token: str):
        self.bot_key = bot_key
        self.bot_meta = bot_meta
        self.token = token
        self.display_name = bot_meta.get("bot_display_name", bot_key)
        self.app_id = bot_meta.get("app_id") or bot_meta.get("application_id", "")
        self.public_key = bot_meta.get("public_key", "")
        self.guild_id = bot_meta.get("guild_id", "")
        self.default_channel_id = bot_meta.get("default_channel_id", "")

        self._ws: ClientConnection | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_interval: float = 41250.0  # discord default fallback
        self._sequence: int | None = None
        self._session_id: str | None = None
        self._running = False
        self._reconnect_attempt = 0
        self._on_message: Any = None  # callback for MESSAGE_CREATE
        self._on_interaction: Any = None  # callback for INTERACTION_CREATE

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._running

    @property
    def status(self) -> str:
        if self.connected:
            return "connected"
        if self._reconnect_attempt > 0:
            return "reconnecting"
        return "disconnected"

    def status_dict(self) -> dict[str, Any]:
        return {
            "bot_key": self.bot_key,
            "display_name": self.display_name,
            "app_id": self.app_id,
            "guild_id": self.guild_id,
            "default_channel_id": self.default_channel_id,
            "connection_status": self.status,
            "session_id": self._session_id[:8] + "..." if self._session_id else None,
            "sequence": self._sequence,
            "reconnect_attempt": self._reconnect_attempt,
        }

    async def connect(self) -> None:
        """Connect to Discord Gateway and start heartbeat loop."""
        self._running = True
        self._reconnect_attempt = 0

        while self._running:
            try:
                await self._connect_once()
                self._reconnect_attempt = 0
                # Block on message loop until disconnect
                await self._message_loop()
            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    OSError,
                    asyncio.TimeoutError) as e:
                self._reconnect_attempt += 1
                delay = min(RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempt - 1)),
                           RECONNECT_MAX_DELAY)
                logger.warning(
                    f"[{self.display_name}] Disconnected (attempt {self._reconnect_attempt}), "
                    f"reconnecting in {delay:.1f}s: {e}"
                )
                await self._cleanup()
                if self._running:
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"[{self.display_name}] Fatal error: {e}")
                await self._cleanup()
                if self._running:
                    await asyncio.sleep(RECONNECT_BASE_DELAY)

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        await self._cleanup()

    async def _connect_once(self) -> None:
        """Establish a single WebSocket connection and identify."""
        logger.info(f"[{self.display_name}] Connecting to Discord Gateway...")
        self._ws = await websockets.connect(DISCORD_GATEWAY_URL, max_size=2 ** 23)
        # Wait for Hello
        raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
        hello = json.loads(raw)
        if hello.get("op") != 10:
            raise RuntimeError(f"Expected Hello (op 10), got op {hello.get('op')}")
        self._heartbeat_interval = max(1.0, (hello["d"]["heartbeat_interval"] - 5000) / 1000.0)
        logger.info(f"[{self.display_name}] Hello received, heartbeat={self._heartbeat_interval:.0f}s")
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        # Send Identify
        intents = DEFAULT_INTENTS
        logger.info(
            f"[{self.display_name}] Gateway intents: {intents} "
            f"GUILDS={bool(intents & (1 << 0))} "
            f"GUILD_MESSAGES={bool(intents & (1 << 9))} "
            f"MESSAGE_CONTENT={bool(intents & (1 << 15))} "
            f"GUILD_MEMBERS={bool(intents & (1 << 1))} "
            f"DIRECT_MESSAGES={bool(intents & (1 << 12))}"
        )
        identify = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": intents,
                "properties": {
                    "os": "windows",
                    "browser": "echora",
                    "device": "echora",
                },
            },
        }
        await self._ws.send(json.dumps(identify))
        logger.info(f"[{self.display_name}] Identify sent, waiting for READY...")

    async def _message_loop(self) -> None:
        """Main receive loop, dispatches to handlers."""
        if self._ws is None:
            return
        while self._running:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=HEARTBEAT_TIMEOUT + 30)
            payload = json.loads(raw)
            op = payload.get("op")
            seq = payload.get("s")
            if seq is not None:
                self._sequence = seq
            t = payload.get("t")
            if op == 0:
                await self._handle_dispatch(t, payload["d"])
            elif op == 1:
                await self._send_heartbeat()
            elif op == 7:
                logger.info(f"[{self.display_name}] Reconnect requested by Discord")
                raise websockets.exceptions.ConnectionClosed(None, None)
            elif op == 9:
                logger.warning(f"[{self.display_name}] Invalid session, re-identifying...")
                await self._cleanup()
                return
            elif op == 11:
                pass  # Heartbeat ACK

    async def _handle_dispatch(self, event_type: str, data: dict[str, Any]) -> None:
        if event_type == "READY":
            self._session_id = data.get("session_id")
            bot_user = data.get("user", {})
            self.bot_meta["bot_user_id"] = bot_user.get("id", "")
            self.bot_meta["bot_username"] = bot_user.get("username", "")
            self.bot_meta["bot_discriminator"] = bot_user.get("discriminator", "0")
            logger.info(
                f"[{self.display_name}] READY — "
                f"user={bot_user.get('username')}#{bot_user.get('discriminator')} "
                f"(id={bot_user.get('id')}) "
                f"session={self._session_id[:8] if self._session_id else '?'}..."
            )
            self._reconnect_attempt = 0
            # Resolve managed bot role from guild
            asyncio.create_task(self._resolve_bot_roles())
        elif event_type == "MESSAGE_CREATE" and self._on_message:
            await self._on_message(self.bot_key, data)
        elif event_type == "INTERACTION_CREATE" and self._on_interaction:
            await self._on_interaction(self.bot_key, data)

    async def _heartbeat_loop(self) -> None:
        while self._running and self._ws is not None:
            await asyncio.sleep(self._heartbeat_interval)
            await self._send_heartbeat()

    async def _send_heartbeat(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"op": 1, "d": self._sequence}))
        except Exception:
            pass

    async def _resolve_bot_roles(self) -> None:
        """Fetch guild roles to map managed bot role_id → bot_key."""
        guild_id = self.bot_meta.get("guild_id", "")
        if not guild_id or not self.token:
            return
        try:
            import httpx
            url = f"https://discord.com/api/v10/guilds/{guild_id}/roles"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bot {self.token}"})
                if resp.status_code != 200:
                    logger.warning(f"[{self.display_name}] Failed to fetch guild roles: {resp.status_code}")
                    return
                roles = resp.json()
                bot_user_id = self.bot_meta.get("bot_user_id", "")
                found_roles = []
                for role in roles:
                    tags = role.get("tags", {}) or {}
                    if tags.get("bot_id") == bot_user_id:
                        role_id = role["id"]
                        _BOT_ROLE_CACHE[role_id] = self.bot_key
                        found_roles.append(role_id)
                if found_roles:
                    logger.info(
                        f"[{self.display_name}] Bot role mapped: role_ids={found_roles} → {self.bot_key}"
                    )
        except Exception as e:
            logger.warning(f"[{self.display_name}] Role resolution skipped: {e}")

    async def _cleanup(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._session_id = None


class DiscordGatewayRuntime:
    """Manages multiple DiscordGatewayBot instances from the bot registry."""

    def __init__(self):
        self._bots: dict[str, DiscordGatewayBot] = {}

    def load_bots(self) -> dict[str, DiscordGatewayBot]:
        """Load all active bots from registry and resolve their tokens."""
        registry = _load_registry()
        for item in registry.get("bots", []):
            bot_key = item.bot_key if hasattr(item, 'bot_key') else item.get("bot_key", "")
            if not bot_key or bot_key in self._bots:
                continue
            token = _resolve_token(item, registry)
            if not token:
                logger.warning("[%s] Configured Discord credential could not be resolved; skipping", bot_key)
                continue
            display_name = item.bot_display_name if hasattr(item, 'bot_display_name') else item.get("display_name", bot_key)
            app_id = item.app_id if hasattr(item, 'app_id') else item.get("app_id", "")
            public_key = item.public_key if hasattr(item, 'public_key') else item.get("public_key", "")
            guild_id = item.guild_id if hasattr(item, 'guild_id') else item.get("guild_id", "")
            default_channel_id = item.default_channel_id if hasattr(item, 'default_channel_id') else item.get("default_channel_id", "")
            bot = DiscordGatewayBot(
                bot_key=bot_key,
                bot_meta={
                    "bot_display_name": display_name,
                    "app_id": app_id,
                    "public_key": public_key,
                    "guild_id": guild_id,
                    "default_channel_id": default_channel_id,
                },
                token=token,
            )
            self._bots[bot_key] = bot
        return self._bots

    async def connect_all(self, on_message: Any = None, on_interaction: Any = None) -> None:
        """Connect all loaded bots to Discord Gateway."""
        if not self._bots:
            self.load_bots()
        for bot in self._bots.values():
            if on_message:
                bot._on_message = on_message
            if on_interaction:
                bot._on_interaction = on_interaction
        tasks = [bot.connect() for bot in self._bots.values()]
        if tasks:
            await asyncio.gather(*tasks)

    async def disconnect_all(self) -> None:
        tasks = [bot.disconnect() for bot in self._bots.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def status_all(self) -> dict[str, Any]:
        bots_status = {}
        for key, bot in self._bots.items():
            bots_status[key] = bot.status_dict()
        registry = _load_registry()
        return {
            "provider": "discord",
            "bots": bots_status,
            "total": len(bots_status),
            "registry_loaded": registry.get("status") == "loaded",
        }


def resolve_role_mention(role_id: str) -> str | None:
    """Check if a role_id maps to a known bot. Returns bot_key or None."""
    return _BOT_ROLE_CACHE.get(role_id)


def get_role_cache() -> dict[str, str]:
    """Return a copy of the bot role cache."""
    return dict(_BOT_ROLE_CACHE)
