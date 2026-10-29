"""
mcpie configuration.

Everything that defines "your usual" lives in one TOML file. Search order:

  1. $MCPIE_CONFIG (explicit path)
  2. ~/.config/mcpie/config.toml
  3. ./mcpie.toml (current working directory)

No PII ever lives in this package or its repo — only in your local config
file. See config.example.toml for the full schema. Card / gift-card details
live in a separate payment.toml written by `mcpie setup-payment` (see
payment.py) — never in this file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

SEARCH_PATHS = [
    Path.home() / ".config" / "mcpie" / "config.toml",
    Path.cwd() / "mcpie.toml",
]

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class ConfigError(Exception):
    """Raised when the config file is missing or malformed."""


@dataclass
class Item:
    code: str
    options: dict = field(default_factory=dict)
    label: str = ""
    qty: int = 1


@dataclass
class Config:
    path: Path
    country: str
    store_id: str
    service_method: str
    customer_first: str
    customer_last: str
    customer_email: str
    customer_phone: str
    addr_street: str
    addr_city: str
    addr_region: str
    addr_zip: str
    items: list[Item]
    user_agent: str = BROWSER_UA
    addr_type: str = "House"
    addr_unit: str = ""
    delivery_store_id: str = ""

    @property
    def order_label(self) -> str:
        return " + ".join(
            (f"{i.qty}x " if i.qty > 1 else "") + (i.label or i.code)
            for i in self.items
        )


def config_path() -> Path | None:
    """Return the first config path that exists, or None."""
    env = os.environ.get("MCPIE_CONFIG")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    for p in SEARCH_PATHS:
        if p.exists():
            return p
    return None


def load() -> Config:
    """Load and validate the config file. Raises ConfigError with a
    human-actionable message on any problem."""
    p = config_path()
    if p is None:
        raise ConfigError(
            "No config file found. Create ~/.config/mcpie/config.toml "
            "(see config.example.toml in the mcpie repo), or point "
            "$MCPIE_CONFIG at one. Tip: the pizza_find_store tool can help "
            "you find your store_id once the address section is filled in."
        )
    try:
        with open(p, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{p} is not valid TOML: {e}") from e

    def need(section: dict, key: str, where: str) -> str:
        v = section.get(key)
        if v in (None, ""):
            raise ConfigError(f"{p}: missing required key '{key}' in [{where}]")
        return str(v)

    cust = raw.get("customer") or {}
    addr = raw.get("address") or {}

    items_raw = raw.get("items") or []
    if not items_raw:
        raise ConfigError(
            f"{p}: no [[items]] defined. Add at least one item with a "
            "product 'code' (use the pizza_menu tool to find codes)."
        )
    items = []
    for i, it in enumerate(items_raw):
        code = it.get("code")
        if not code:
            raise ConfigError(f"{p}: items[{i}] is missing 'code'")
        items.append(
            Item(
                code=str(code),
                options=it.get("options") or {},
                label=str(it.get("label") or ""),
                qty=int(it.get("qty") or 1),
            )
        )

    country = str(raw.get("country") or "us").lower()
    if country not in ("us", "ca"):
        raise ConfigError(f"{p}: country must be 'us' or 'ca' (got '{country}')")

    service = str(raw.get("service_method") or "Carryout")
    if service not in ("Carryout", "Delivery"):
        raise ConfigError(
            f"{p}: service_method must be 'Carryout' or 'Delivery' (got '{service}')"
        )

    return Config(
        path=p,
        country=country,
        store_id=need(raw, "store_id", "top level"),
        service_method=service,
        customer_first=need(cust, "first", "customer"),
        customer_last=need(cust, "last", "customer"),
        customer_email=need(cust, "email", "customer"),
        customer_phone=need(cust, "phone", "customer"),
        addr_street=need(addr, "street", "address"),
        addr_city=need(addr, "city", "address"),
        addr_region=need(addr, "region", "address"),
        addr_zip=need(addr, "zip", "address"),
        items=items,
        addr_type=str(addr.get("type") or "House"),
        addr_unit=str(addr.get("unit") or ""),
        delivery_store_id=str(raw.get("delivery_store_id") or ""),
    )
