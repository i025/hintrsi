from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_config_data(config_path: Optional[str]) -> Dict[str, Any]:
    if not config_path:
        return {}

    path = Path(config_path)
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(raw)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to load YAML config files") from exc
        data = yaml.safe_load(raw)
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                import yaml
            except ImportError as exc:
                raise RuntimeError(
                    f"Unsupported config format for {path}. Use JSON, or install PyYAML for YAML."
                ) from exc
            data = yaml.safe_load(raw)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping at the top level: {path}")
    return data


def _apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    endpoints_json = _clean_optional(os.getenv("CC_ROUTING_ENDPOINTS_JSON"))
    if not endpoints_json:
        return data

    try:
        endpoints = json.loads(endpoints_json)
    except json.JSONDecodeError as exc:
        raise ValueError("CC_ROUTING_ENDPOINTS_JSON must be a valid JSON array") from exc

    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("CC_ROUTING_ENDPOINTS_JSON must be a non-empty JSON array")
    invalid_indexes = [
        str(index)
        for index, endpoint in enumerate(endpoints)
        if not isinstance(endpoint, dict)
    ]
    if invalid_indexes:
        raise ValueError(
            "CC_ROUTING_ENDPOINTS_JSON entries must be JSON objects; "
            f"invalid indexes: {', '.join(invalid_indexes)}"
        )

    routing = data.setdefault("routing", {})
    if not isinstance(routing, dict):
        raise ValueError("run_config.routing must be a mapping when using CC_ROUTING_ENDPOINTS_JSON")
    routing["endpoints"] = endpoints
    return data


@dataclass
class EndpointConfig:
    api_base: str
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    weight: int = 1
    name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EndpointConfig":
        api_base = str(data.get("api_base", "")).strip()
        if not api_base:
            raise ValueError("Each routing endpoint must define a non-empty api_base")
        weight = int(data.get("weight", 1))
        if weight <= 0:
            raise ValueError(f"Endpoint weight must be > 0 for {api_base}")
        name = data.get("name")
        return cls(
            api_base=api_base,
            provider=_clean_optional(data.get("provider")),
            model=_clean_optional(data.get("model")),
            api_key=_clean_optional(data.get("api_key")),
            weight=weight,
            name=str(name).strip() if name else None,
        )

    def to_backend(self) -> "BackendConfig":
        return BackendConfig(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base,
        )


@dataclass
class BackendConfig:
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["BackendConfig"]:
        if data is None:
            return None
        return cls(
            provider=_clean_optional(data.get("provider")),
            model=_clean_optional(data.get("model")),
            api_key=_clean_optional(data.get("api_key")),
            api_base=_clean_optional(data.get("api_base")),
        )

    def merge(self, base: "BackendConfig") -> "BackendConfig":
        return BackendConfig(
            provider=self.provider or base.provider,
            model=self.model or base.model,
            api_key=self.api_key or base.api_key,
            api_base=self.api_base or base.api_base,
        )

    def with_api_base(self, api_base: str) -> "BackendConfig":
        return BackendConfig(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            api_base=api_base,
        )

    def require_complete(self, label: str) -> "BackendConfig":
        missing = [
            field_name
            for field_name in ("provider", "model", "api_key", "api_base")
            if not getattr(self, field_name)
        ]
        if missing:
            raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
        return self

    @property
    def litellm_model(self) -> str:
        self.require_complete("LLM backend")
        return f"{self.provider}/{self.model}"


@dataclass
class RoutingConfig:
    strategy: str = "weighted_random"
    endpoints: List[EndpointConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RoutingConfig":
        data = data or {}
        endpoints = [
            EndpointConfig.from_dict(item)
            for item in data.get("endpoints", [])
        ]
        strategy = str(data.get("strategy", "weighted_random")).strip() or "weighted_random"
        return cls(strategy=strategy, endpoints=endpoints)

    def select_endpoint(self) -> EndpointConfig:
        if not self.endpoints:
            raise ValueError("routing.endpoints must contain at least one endpoint")
        if self.strategy != "weighted_random":
            raise ValueError(f"Unsupported routing strategy: {self.strategy}")
        weights = [endpoint.weight for endpoint in self.endpoints]
        return random.choices(self.endpoints, weights=weights, k=1)[0]


@dataclass
class VerificationConfig:
    mode: str = "same_as_execution"
    backend: Optional[BackendConfig] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "VerificationConfig":
        data = data or {}
        mode = str(data.get("mode", "same_as_execution")).strip() or "same_as_execution"
        return cls(mode=mode, backend=BackendConfig.from_dict(data.get("backend")))

    def resolve(self, execution_backend: BackendConfig) -> BackendConfig:
        if self.mode == "same_as_execution":
            return execution_backend
        if self.mode == "explicit":
            if self.backend is None:
                raise ValueError("verification.backend must be set when verification.mode=explicit")
            return self.backend.merge(execution_backend).require_complete("verification backend")
        raise ValueError(f"Unsupported verification mode: {self.mode}")


@dataclass
class ProxyConfig:
    listen_base_url: str = "http://localhost:4000"
    auth_token: str = "sk-111"
    callbacks_path: str = "/tmp/litellm_call_backs.proxy_handler_instance"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ProxyConfig":
        data = data or {}
        return cls(
            listen_base_url=str(data.get("listen_base_url", "http://localhost:4000")).strip(),
            auth_token=str(data.get("auth_token", "sk-111")).strip(),
            callbacks_path=str(
                data.get("callbacks_path", "/tmp/litellm_call_backs.proxy_handler_instance")
            ).strip(),
        )


@dataclass
class ContainerProxyConfig:
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    no_proxy: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ContainerProxyConfig":
        data = data or {}
        return cls(
            http_proxy=_clean_optional(data.get("http_proxy")),
            https_proxy=_clean_optional(data.get("https_proxy")),
            no_proxy=_clean_optional(data.get("no_proxy")),
        )

    def build_env(self) -> Dict[str, str]:
        env: Dict[str, str] = {}
        proxy_values = {
            "http_proxy": self.http_proxy,
            "https_proxy": self.https_proxy,
            "no_proxy": self.no_proxy,
        }
        for key, value in proxy_values.items():
            if value:
                env[key] = value
                env[key.upper()] = value
        return env


@dataclass
class SDKConfig:
    anthropic_model: Optional[str] = None
    anthropic_small_fast_model: Optional[str] = None
    api_timeout_ms: int = 600000
    disable_nonessential_traffic: bool = True
    is_sandbox: bool = True
    first_init: bool = False

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SDKConfig":
        data = data or {}
        return cls(
            anthropic_model=_clean_optional(data.get("anthropic_model")),
            anthropic_small_fast_model=_clean_optional(data.get("anthropic_small_fast_model")),
            api_timeout_ms=int(data.get("api_timeout_ms", 600000)),
            disable_nonessential_traffic=bool(data.get("disable_nonessential_traffic", True)),
            is_sandbox=bool(data.get("is_sandbox", True)),
            first_init=bool(data.get("first_init", False)),
        )

    def build_env(self, proxy: ProxyConfig, routed_backend: BackendConfig) -> Dict[str, str]:
        anthropic_model = self.anthropic_model or routed_backend.model
        if not anthropic_model:
            raise ValueError("sdk.anthropic_model is not set and routed backend has no model")
        if not anthropic_model.endswith("[1m]"):
            anthropic_model += "[1m]"
        small_fast_model = self.anthropic_small_fast_model or anthropic_model
        if not small_fast_model.endswith("[1m]"):
            small_fast_model += "[1m]"
        env = {
            "ANTHROPIC_BASE_URL": proxy.listen_base_url,
            "ANTHROPIC_AUTH_TOKEN": proxy.auth_token,
            "API_TIMEOUT_MS": str(self.api_timeout_ms),
            "ANTHROPIC_MODEL": anthropic_model,
            "ANTHROPIC_SMALL_FAST_MODEL": small_fast_model,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1" if self.disable_nonessential_traffic else "0",
            "IS_SANDBOX": "1" if self.is_sandbox else "0",
        }
        auto_compact = os.getenv("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
        if auto_compact:
            env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = auto_compact
        disable_auto_compact = os.getenv("DISABLE_AUTO_COMPACT")
        if disable_auto_compact:
            env["DISABLE_AUTO_COMPACT"] = disable_auto_compact
        max_output_tokens = os.getenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS")
        if max_output_tokens:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = max_output_tokens
        return env


@dataclass
class ResolvedTaskConfig:
    selected_endpoint: EndpointConfig
    execution_backend: BackendConfig
    verification_backend: BackendConfig
    proxy: ProxyConfig
    container_proxy: ContainerProxyConfig
    sdk: SDKConfig
    container_env: Dict[str, str]
    claude_env: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunConfig:
    routing: RoutingConfig
    verification: VerificationConfig
    proxy: ProxyConfig
    container_proxy: ContainerProxyConfig
    sdk: SDKConfig

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunConfig":
        if "routing" not in data or not data.get("routing"):
            raise ValueError("run_config must define 'routing'")
        return cls(
            routing=RoutingConfig.from_dict(data.get("routing")),
            verification=VerificationConfig.from_dict(data.get("verification")),
            proxy=ProxyConfig.from_dict(data.get("proxy")),
            container_proxy=ContainerProxyConfig.from_dict(data.get("container_proxy")),
            sdk=SDKConfig.from_dict(data.get("sdk")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def resolve_task(self) -> ResolvedTaskConfig:
        endpoint = self.routing.select_endpoint()
        execution_backend = endpoint.to_backend().require_complete("execution backend")
        verification_backend = self.verification.resolve(execution_backend)
        container_env = self.container_proxy.build_env()
        claude_env = {**container_env, **self.sdk.build_env(self.proxy, execution_backend)}
        return ResolvedTaskConfig(
            selected_endpoint=endpoint,
            execution_backend=execution_backend,
            verification_backend=verification_backend,
            proxy=self.proxy,
            container_proxy=self.container_proxy,
            sdk=self.sdk,
            container_env=container_env,
            claude_env=claude_env,
        )

def load_run_config(config_path: Optional[str]) -> RunConfig:
    if not config_path:
        raise ValueError("A config file path is required; no default configuration is provided")
    raw_config = _load_config_data(config_path)
    if not raw_config:
        raise ValueError(f"Config file is empty: {config_path}")
    raw_config = _apply_env_overrides(raw_config)
    return RunConfig.from_dict(raw_config)


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None