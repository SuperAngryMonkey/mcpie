"""
Domino's order logic for mcpie.

Wraps the `pizzapi` library and works around four of its quirks
(inherited from the battle-tested stimpy appliance this project grew
out of):

  1. It sends bare requests with no User-Agent. Domino's 403s requests
     without browser-like headers from many networks, so we monkeypatch
     requests to inject a UA on every call the library makes.
  2. `Order.add_item(options=...)` is a documented no-op (the library
     has a literal "TODO: Implement item options"). We inject toppings
     into the product dict manually after add_item.
  3. `Order` defaults ServiceMethod to "Delivery". We set it per order.
  4. `Menu.build_categories` raises "PRODUCT NOT FOUND" when Domino's
     Categorization tree references coupon-only product codes that don't
     appear in the flat menu. We monkeypatch it to skip orphan refs.

Payment is cash by default. Since v0.2 a card or gift card may be
configured in a separate local payment file (see payment.py); it is read
at order time only, and every Domino's response is scrubbed of card
fields before it leaves this module.
"""

from __future__ import annotations

import requests

from . import payment
from .config import Config

# --- Quirk 1: inject a browser UA on every request the library makes ---
_orig_get = requests.get
_orig_post = requests.post
_UA = {"value": None}


def _get(url, **kw):
    h = kw.pop("headers", {}) or {}
    if _UA["value"]:
        h.setdefault("User-Agent", _UA["value"])
    return _orig_get(url, headers=h, **kw)


def _post(url, **kw):
    h = kw.pop("headers", {}) or {}
    if _UA["value"]:
        h.setdefault("User-Agent", _UA["value"])
    return _orig_post(url, headers=h, **kw)


requests.get = _get
requests.post = _post

# Import pizzapi AFTER patching so its module-level usage picks up the patch.
from pizzapi import Address, Customer, Order, Store  # noqa: E402
from pizzapi.menu import Menu, MenuCategory  # noqa: E402


# --- Quirk 4: tolerate orphan product refs in Categorization ---
def _build_categories_forgiving(self, category_data, parent=None):
    category = MenuCategory(category_data, parent)
    for subcategory in category_data.get("Categories", []):
        category.subcategories.append(
            _build_categories_forgiving(self, subcategory, category)
        )
    for product_code in category_data.get("Products", []):
        product = self.menu_by_code.get(product_code)
        if product is None:
            continue  # orphan reference (coupon-only product, etc)
        product.categories.append(category)
        category.products.append(product)
    return category


Menu.build_categories = _build_categories_forgiving

CARRYOUT, DELIVERY = "Carryout", "Delivery"
_MODES = {"carryout": CARRYOUT, "delivery": DELIVERY}
_DELIVERY_STORE: dict[str, str] = {}


class OrderError(Exception):
    """Raised when an order can't be built or validated."""


def _host(cfg: Config) -> str:
    return "order.dominos.ca" if cfg.country == "ca" else "order.dominos.com"


def _activate(cfg: Config) -> None:
    """Arm the UA patch with the configured user agent."""
    _UA["value"] = cfg.user_agent


def normalize_mode(cfg: Config, mode: str | None) -> str:
    m = _MODES.get(str(mode or "").strip().lower())
    if mode and not m:
        raise OrderError(f"unknown mode '{mode}' (use carryout or delivery)")
    return m or cfg.service_method


def _locator(cfg: Config, service: str) -> list[dict]:
    r = requests.get(
        f"https://{_host(cfg)}/power/store-locator",
        params={
            "s": cfg.addr_street,
            "c": f"{cfg.addr_city}, {cfg.addr_region} {cfg.addr_zip}",
            "type": service,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("Stores", [])


def delivery_store_id(cfg: Config) -> str:
    """Store that delivers to the configured address: config wins, else
    the nearest open store with Delivery service, cached per process."""
    if cfg.delivery_store_id:
        return cfg.delivery_store_id
    key = f"{cfg.addr_street}|{cfg.addr_zip}"
    if key in _DELIVERY_STORE:
        return _DELIVERY_STORE[key]
    _activate(cfg)
    for s in _locator(cfg, DELIVERY):
        if s.get("IsOnlineNow") and (s.get("ServiceIsOpen") or {}).get(DELIVERY):
            _DELIVERY_STORE[key] = str(s["StoreID"])
            return _DELIVERY_STORE[key]
    raise OrderError("No Domino's store currently delivers to the configured address.")


def store_for(cfg: Config, mode: str) -> str:
    return delivery_store_id(cfg) if mode == DELIVERY else cfg.store_id


def build_order(cfg: Config, coupon_code: str | None = None, mode: str | None = None):
    """Construct the configured standing order. Returns (Order, Customer).

    mode: "carryout" | "delivery" (default: cfg.service_method).
    Optionally attaches a coupon by code. Whether Domino's actually applies
    it is determined at validate/price time — they accept-with-discount,
    accept-without-effect, or reject (Status: -1).
    """
    _activate(cfg)
    mode = normalize_mode(cfg, mode)
    customer = Customer(
        cfg.customer_first, cfg.customer_last, cfg.customer_email, cfg.customer_phone
    )
    address = Address(
        cfg.addr_street, cfg.addr_city, cfg.addr_region, cfg.addr_zip,
        country=cfg.country,
    )

    store = Store({"StoreID": store_for(cfg, mode)}, country=cfg.country)
    order = Order(store, customer, address, country=cfg.country)

    # Quirk 3: service method per order, not the library default.
    order.data["ServiceMethod"] = mode
    order.data["Address"]["Type"] = cfg.addr_type
    if cfg.addr_unit:
        order.data["Address"]["UnitNumber"] = cfg.addr_unit

    for item in cfg.items:
        added = order.add_item(item.code, qty=item.qty)
        # Quirk 2: inject toppings/options manually.
        if item.options:
            added["Options"] = dict(item.options)

    # Coupon: direct dict append — the library's add_coupon() looks up
    # menu.variants, which doesn't contain coupon entries.
    if coupon_code:
        order.data["Coupons"].append({"Code": str(coupon_code), "Qty": 1})

    return order, customer


def validate_order(cfg: Config, order, pay: str | None = None) -> str:
    """Validate + price the order without placing it. Returns quoted amount.

    `pay`: cash | card | giftcard (default: the payment file's type, else
    cash). The matching Payments entry is attached so Domino's validates
    its shape; it is never logged or returned.
    """
    if not order.validate():
        raise OrderError(
            "Domino's rejected the order at validation. The store may be "
            "closed, an item may be unavailable, or a product code may have "
            "drifted. Use pizza_menu to re-verify codes."
        )
    # pay_with(False) prices the order (and sets Cash, which we overwrite).
    resp = order.pay_with(False)
    amount = resp.get("Order", {}).get("Amounts", {}).get("Customer")
    ptype = payment.normalize(pay) if pay else payment.configured_type(cfg.path)
    delivery = order.data.get("ServiceMethod") == DELIVERY
    order.data["Payments"] = [
        payment.build_payment(ptype, amount, delivery=delivery, config_file=cfg.path)
    ]
    return amount


def total_due(order) -> str:
    """Quote + tip, from the Payments entry validate_order set."""
    p = (order.data.get("Payments") or [{}])[0]
    amt = p.get("Amount")
    if amt is None:
        return str(order.data.get("Amounts", {}).get("Customer"))
    return f"{float(amt) + float(p.get('TipAmount') or 0):.2f}"


def place_order(order) -> dict:
    """Place the order for real with the Payments validate_order set.

    Bypasses pizzapi's Order.place(), which would reset Payments to Cash.
    The response is scrubbed of card fields before it is returned.
    """
    resp = order._send(order.urls.place_url(), False)  # noqa: SLF001
    return payment.scrub(resp)


def sniff_menu(cfg: Config, query: str) -> dict:
    """Search the configured store's live menu for product/topping codes."""
    _activate(cfg)
    q = query.lower()
    r = requests.get(
        f"https://{_host(cfg)}/power/store/{cfg.store_id}/menu"
        "?lang=en&structured=true",
        timeout=15,
    )
    r.raise_for_status()
    m = r.json()

    out = {"variants": [], "toppings": {}}
    for code, v in m.get("Variants", {}).items():
        if q in v.get("Name", "").lower():
            out["variants"].append({"code": code, "name": v["Name"]})
    for category, toppings in (m.get("Toppings") or {}).items():
        hits = [
            {"code": code, "name": t.get("Name", "")}
            for code, t in toppings.items()
            if q in t.get("Name", "").lower()
        ]
        if hits:
            out["toppings"][category] = hits
    return out


def list_specials(cfg: Config, mode: str | None = None) -> list[dict]:
    """Active coupons valid for the given service method at the store that
    serves it, cheapest first. Read-only; never applies anything."""
    _activate(cfg)
    mode = normalize_mode(cfg, mode)
    r = requests.get(
        f"https://{_host(cfg)}/power/store/{store_for(cfg, mode)}/menu"
        "?lang=en&structured=true",
        timeout=15,
    )
    r.raise_for_status()
    m = r.json()

    out = []
    for code, v in m.get("Coupons", {}).items():
        tags = v.get("Tags", {}) or {}
        methods = tags.get("ValidServiceMethods", []) or []
        if mode not in methods:
            continue
        name = (v.get("Name") or "").strip()
        if not name:
            continue  # internal upsell stubs
        try:
            price_f = float(v.get("Price") or 0)
        except (TypeError, ValueError):
            price_f = 0.0
        out.append(
            {
                "code": code,
                "name": name,
                "price": v.get("Price") or "",
                "price_f": price_f,
                "methods": methods,
                "bundle": bool(v.get("Bundle")),
                "effective": tags.get("EffectiveOn", ""),
            }
        )
    out.sort(key=lambda x: (x["price_f"] == 0, x["price_f"]))
    return out


def find_stores(cfg: Config) -> list[dict]:
    """Nearest Domino's stores for the configured address. Read-only.
    Helps first-time users discover their store_id."""
    _activate(cfg)
    stores = _locator(cfg, cfg.service_method)[:8]
    return [
        {
            "store_id": s.get("StoreID"),
            "address": s.get("AddressDescription", "").replace("\n", ", "),
            "phone": s.get("Phone"),
            "open_now": s.get("IsOpen"),
            "allows_carryout": s.get("ServiceIsOpen", {}).get("Carryout"),
            "allows_delivery": s.get("ServiceIsOpen", {}).get("Delivery"),
            "distance": s.get("MinDistance"),
        }
        for s in stores
    ]


def store_reachable(cfg: Config) -> bool:
    """Cheap liveness probe of the configured store's profile endpoint."""
    _activate(cfg)
    try:
        r = requests.get(
            f"https://{_host(cfg)}/power/store/{cfg.store_id}/profile",
            timeout=10,
        )
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False
