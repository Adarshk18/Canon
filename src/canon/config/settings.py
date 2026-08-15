from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from canon.config.paths import ProjectPaths, user_config_path
from canon.constants import (
    DEFAULT_LOOKBACK_COMMITS,
    DEFAULT_LOOKBACK_PRS,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_DECISIONS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MIN_SCORE,
    SCHEMA_VERSION,
)
from canon.errors import ConfigError


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Expected an integer, got {value!r}.") from exc


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Expected a boolean, got {value!r}.")


@dataclass(slots=True)
class InjectionSettings:
    max_decisions: int = DEFAULT_MAX_DECISIONS
    max_chars: int = DEFAULT_MAX_CHARS
    max_tokens: int = DEFAULT_MAX_TOKENS


@dataclass(slots=True)
class MiningSettings:
    lookback_prs: int = DEFAULT_LOOKBACK_PRS
    lookback_commits: int = DEFAULT_LOOKBACK_COMMITS
    min_score: int = DEFAULT_MIN_SCORE


@dataclass(slots=True)
class IntegrationSettings:
    claude: bool = True
    cursor: bool = True


@dataclass(slots=True)
class PrivacySettings:
    telemetry: bool = False


@dataclass(slots=True)
class Settings:
    schema_version: int = SCHEMA_VERSION
    injection: InjectionSettings = field(default_factory=InjectionSettings)
    mining: MiningSettings = field(default_factory=MiningSettings)
    integrations: IntegrationSettings = field(default_factory=IntegrationSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    debug: bool = False

    def to_toml(self) -> str:
        lines = [
            "# Canon project configuration",
            f"schema_version = {self.schema_version}",
            "",
            "[injection]",
            f"max_decisions = {self.injection.max_decisions}",
            f"max_chars = {self.injection.max_chars}",
            f"max_tokens = {self.injection.max_tokens}",
            "",
            "[mining]",
            f"lookback_prs = {self.mining.lookback_prs}",
            f"lookback_commits = {self.mining.lookback_commits}",
            f"min_score = {self.mining.min_score}",
            "",
            "[integrations]",
            f"claude = {'true' if self.integrations.claude else 'false'}",
            f"cursor = {'true' if self.integrations.cursor else 'false'}",
            "",
            "[privacy]",
            f"telemetry = {'true' if self.privacy.telemetry else 'false'}",
            "",
        ]
        return "\n".join(lines)

    def get(self, dotted: str) -> Any:
        mapping = self.as_dict()
        current: Any = mapping
        for part in dotted.split("."):
            if not isinstance(current, dict) or part not in current:
                raise ConfigError(f"Unknown setting: {dotted}")
            current = current[part]
        return current

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "debug": self.debug,
            "injection": {
                "max_decisions": self.injection.max_decisions,
                "max_chars": self.injection.max_chars,
                "max_tokens": self.injection.max_tokens,
            },
            "mining": {
                "lookback_prs": self.mining.lookback_prs,
                "lookback_commits": self.mining.lookback_commits,
                "min_score": self.mining.min_score,
            },
            "integrations": {
                "claude": self.integrations.claude,
                "cursor": self.integrations.cursor,
            },
            "privacy": {"telemetry": self.privacy.telemetry},
        }


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read config file: {path}") from exc
    return data if isinstance(data, dict) else {}


def _from_mapping(data: dict[str, Any], base: Settings) -> Settings:
    injection = data.get("injection") or {}
    mining = data.get("mining") or {}
    integrations = data.get("integrations") or {}
    privacy = data.get("privacy") or {}
    return Settings(
        schema_version=_as_int(data.get("schema_version"), base.schema_version),
        injection=InjectionSettings(
            max_decisions=_as_int(
                injection.get("max_decisions"), base.injection.max_decisions
            ),
            max_chars=_as_int(injection.get("max_chars"), base.injection.max_chars),
            max_tokens=_as_int(injection.get("max_tokens"), base.injection.max_tokens),
        ),
        mining=MiningSettings(
            lookback_prs=_as_int(mining.get("lookback_prs"), base.mining.lookback_prs),
            lookback_commits=_as_int(
                mining.get("lookback_commits"), base.mining.lookback_commits
            ),
            min_score=_as_int(mining.get("min_score"), base.mining.min_score),
        ),
        integrations=IntegrationSettings(
            claude=_as_bool(integrations.get("claude"), base.integrations.claude),
            cursor=_as_bool(integrations.get("cursor"), base.integrations.cursor),
        ),
        privacy=PrivacySettings(
            telemetry=_as_bool(privacy.get("telemetry"), base.privacy.telemetry)
        ),
        debug=base.debug,
    )


def _apply_env(settings: Settings) -> Settings:
    debug = _as_bool(os.environ.get("CANON_DEBUG"), settings.debug)
    telemetry_env = os.environ.get("CANON_TELEMETRY")
    telemetry = (
        _as_bool(telemetry_env, settings.privacy.telemetry)
        if telemetry_env is not None
        else settings.privacy.telemetry
    )
    return Settings(
        schema_version=settings.schema_version,
        injection=InjectionSettings(
            max_decisions=_as_int(
                os.environ.get("CANON_MAX_DECISIONS"), settings.injection.max_decisions
            ),
            max_chars=_as_int(
                os.environ.get("CANON_MAX_CHARS"), settings.injection.max_chars
            ),
            max_tokens=_as_int(
                os.environ.get("CANON_MAX_TOKENS"), settings.injection.max_tokens
            ),
        ),
        mining=settings.mining,
        integrations=settings.integrations,
        privacy=PrivacySettings(telemetry=telemetry),
        debug=debug,
    )


def load_settings(paths: ProjectPaths | None = None) -> Settings:
    """Precedence: environment > project config > user config > defaults."""
    settings = Settings()
    settings = _from_mapping(_load_toml(user_config_path()), settings)
    if paths is not None:
        settings = _from_mapping(_load_toml(paths.config_file), settings)
    return _apply_env(settings)


def write_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.to_toml(), encoding="utf-8")


def merge_set(settings: Settings, dotted: str, raw: str) -> Settings:
    parts = dotted.split(".")
    data = settings.as_dict()
    cursor: dict[str, Any] = data
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            raise ConfigError(f"Unknown setting: {dotted}")
        cursor = next_value
    key = parts[-1]
    if key not in cursor:
        raise ConfigError(f"Unknown setting: {dotted}")
    current = cursor[key]
    if isinstance(current, bool):
        cursor[key] = _as_bool(raw, current)
    elif isinstance(current, int):
        cursor[key] = _as_int(raw, current)
    else:
        raise ConfigError(f"Setting {dotted} cannot be changed from the CLI.")
    updated = _from_mapping(data, settings)
    return replace(updated, debug=settings.debug)
