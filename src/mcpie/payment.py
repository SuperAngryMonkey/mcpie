"""
Payment handling for mcpie (v0.2).

Three payment types:

  cash      — pay at pickup / pay the driver. The default; needs no secrets.
  card      — credit card held ONLY in a local payment file, never in the
              main config, never accepted from a tool argument, never
              logged or returned.
  giftcard  — Domino's gift card number + PIN, same file, same rules.
              Recommended over a real card: loss is capped at the balance.

The payment file is `payment.toml` next to the config file (so by default
~/.config/mcpie/payment.toml), mode 0600, written only by the interactive
`mcpie setup-payment` command. Override the location with $MCPIE_PAYMENT.

The card number exists in exactly two places: that file, and the single
HTTPS POST to Domino's that places the order. Every Domino's response is
passed through scrub() before anything is logged or returned.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

CASH, CARD, GIFTCARD = "Cash", "CreditCard", "GiftCard"
_ALIASES = {
    "cash": CASH,
    "card": CARD,
    "creditcard": CARD,
    "credit": CARD,
    "giftcard": GIFTCARD,
    "gift": GIFTCARD,
}

_CARD_PATTERNS = {
    "VISA": r"^4[0-9]{12}(?:[0-9]{3})?$",
    "MASTERCARD": r"^(?:5[1-5][0-9]{14}|2(?:2[2-9][0-9]|[3-6][0-9]{2}|7[01][0-9]|720)[0-9]{12})$",
    "AMEX": r"^3[47][0-9]{13}$",
    "DISCOVER": r"^6(?:011|5[0-9]{2})[0-9]{12}$",
}

_SCRUB_KEYS = {"Number", "SecurityCode", "Pin", "Expiration", "PostalCode", "CardType"}


class PaymentError(Exception):
    """Raised when a payment type is requested but not usable."""


def normalize(name: str | None) -> str:
    t = _ALIASES.get(str(name or "cash").strip().lower())
    if not t:
        raise PaymentError(f"unknown pay mode '{name}' (use cash, card or giftcard)")
    return t


def luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def card_type(number: str) -> str:
    return next((t for t, p in _CARD_PATTERNS.items() if re.match(p, number)), "")


def validate_card(number: str, expiration: str, cvv: str, zip_code: str) -> tuple[bool, list[str]]:
    """Return (ok, problems). Problems never include the number."""
    problems = []
    if not re.match(r"^[0-9]{13,19}$", number or ""):
        problems.append("card number must be 13-19 digits")
    elif not luhn_ok(number):
        problems.append("card number fails checksum (typo?)")
    elif not card_type(number):
        problems.append("card type not recognised (Visa/MC/Amex/Discover)")
    if not re.match(r"^(0[1-9]|1[0-2])[0-9]{2}$", expiration or ""):
        problems.append("expiration must be MMYY")
    if not re.match(r"^[0-9]{3,4}$", cvv or ""):
        problems.append("CVV must be 3 or 4 digits")
    if not re.match(r"^[0-9]{5}(?:-[0-9]{4})?$", zip_code or ""):
        problems.append("billing ZIP must be 5 digits")
    return (not problems), problems


# --- payment file -----------------------------------------------------------


def payment_path(config_file: Path | None = None) -> Path:
    env = os.environ.get("MCPIE_PAYMENT")
    if env:
        return Path(env).expanduser()
    base = config_file.parent if config_file else Path.home() / ".config" / "mcpie"
    return base / "payment.toml"


def _load(config_file: Path | None = None) -> dict | None:
    p = payment_path(config_file)
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return tomllib.load(f)


def configured_type(config_file: Path | None = None) -> str:
    raw = _load(config_file)
    if not raw:
        return CASH
    return normalize((raw.get("payment") or {}).get("type", "cash"))


def tip_amount(config_file: Path | None = None) -> float:
    raw = _load(config_file) or {}
    try:
        return round(float((raw.get("payment") or {}).get("delivery_tip", 0) or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def describe(ptype: str, config_file: Path | None = None) -> str:
    """Human label safe to log/return — last 4 digits only."""
    if ptype == CASH:
        return "cash"
    raw = _load(config_file) or {}
    if ptype == CARD:
        n = str((raw.get("card") or {}).get("number", "")).replace(" ", "")
        return f"{card_type(n).title() or 'card'} ending {n[-4:]}" if n else "card (not configured)"
    n = str((raw.get("giftcard") or {}).get("number", "")).replace(" ", "")
    return f"gift card ending {n[-4:]}" if n else "gift card (not configured)"


def build_payment(ptype: str, amount, delivery: bool = False, config_file: Path | None = None) -> dict:
    """Return the Domino's Payments[] entry. `amount` is Order.Amounts.Customer."""
    ptype = normalize(ptype)
    if ptype == CASH:
        return {"Type": CASH}

    raw = _load(config_file)
    if raw is None:
        raise PaymentError(
            f"{ptype} requested but {payment_path(config_file)} does not exist. "
            "Run `mcpie setup-payment` in a terminal first."
        )
    tip = tip_amount(config_file) if delivery else 0.0
    base = {"Amount": float(amount), "TipAmount": tip}

    if ptype == CARD:
        c = raw.get("card") or {}
        number = str(c.get("number", "")).replace(" ", "")
        exp = str(c.get("expiration", ""))
        cvv = str(c.get("cvv", ""))
        zip_code = str(c.get("zip", ""))
        ok, problems = validate_card(number, exp, cvv, zip_code)
        if not ok:
            raise PaymentError("card in payment file is invalid: " + "; ".join(problems))
        return {
            "Type": CARD,
            "CardType": card_type(number),
            "Number": number,
            "Expiration": exp,
            "SecurityCode": cvv,
            "PostalCode": zip_code,
            **base,
        }

    g = raw.get("giftcard") or {}
    number = str(g.get("number", "")).replace(" ", "")
    pin = str(g.get("pin", ""))
    if not (number.isdigit() and pin.isdigit()):
        raise PaymentError("gift card number/PIN missing or non-numeric in payment file")
    return {"Type": GIFTCARD, "Number": number, "Pin": pin, **base}


def scrub(obj):
    """Recursively replace card fields with *** in any Domino's dict."""
    if isinstance(obj, dict):
        return {k: ("***" if k in _SCRUB_KEYS else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


# --- interactive setup (mcpie setup-payment) ---------------------------------


def _ask(label: str, secret: bool = False, default: str = "") -> str:
    import getpass

    prompt = label + (f" [{default}]" if default else "") + ": "
    v = getpass.getpass(prompt) if secret else input(prompt)
    v = v.strip().replace(" ", "")
    return v or default


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def setup_cli(argv: list[str], config_file: Path | None = None) -> int:
    """`mcpie setup-payment [--show|--clear]`. Returns an exit code."""
    target = payment_path(config_file)

    if "--show" in argv:
        if not target.exists():
            print(f"No payment file at {target} — mcpie is cash-only.")
            return 0
        print(f"Payment file    : {target}")
        print(f"Default payment : {describe(configured_type(config_file), config_file)}")
        print(f"Delivery tip    : ${tip_amount(config_file):.2f}")
        mode = target.stat().st_mode & 0o777
        print(f"File mode       : {oct(mode)}" + ("" if mode == 0o600 else "  <-- should be 0600"))
        return 0

    if "--clear" in argv:
        if target.exists():
            target.unlink()
            print(f"{target} removed. mcpie is cash-only again.")
        else:
            print("Nothing to clear.")
        return 0

    try:
        print("mcpie payment setup. Input is masked; nothing is echoed or logged.\n")
        choice = _ask("Default payment type (cash / card / giftcard)", default="cash").lower()
        ptype = normalize(choice)
        lines = [
            "# mcpie payment file — written by `mcpie setup-payment`. Keep it 0600.",
            "[payment]",
            f"type = {_toml_str(choice)}",
        ]
        if ptype == CARD:
            while True:
                number = _ask("Card number", secret=True)
                exp = _ask("Expiration (MMYY)")
                cvv = _ask("CVV", secret=True)
                zip_code = _ask("Billing ZIP")
                ok, problems = validate_card(number, exp, cvv, zip_code)
                if ok:
                    break
                print("  problem: " + "; ".join(problems) + "\n")
            print(f"\n  {card_type(number).title()} ending {number[-4:]}, exp {exp[:2]}/{exp[2:]}")
        elif ptype == GIFTCARD:
            while True:
                number = _ask("Gift card number", secret=True)
                pin = _ask("Gift card PIN", secret=True)
                if number.isdigit() and pin.isdigit():
                    break
                print("  problem: number and PIN must be digits\n")
            print(f"\n  Gift card ending {number[-4:]}")

        tip = _ask("Delivery tip in dollars (delivery orders only)", default="3.00")
        try:
            tip = f"{float(tip):.2f}"
        except ValueError:
            tip = "0.00"
        lines.append(f"delivery_tip = {tip}")

        if ptype == CARD:
            lines += ["", "[card]", f"number = {_toml_str(number)}", f"expiration = {_toml_str(exp)}",
                      f"cvv = {_toml_str(cvv)}", f"zip = {_toml_str(zip_code)}"]
        elif ptype == GIFTCARD:
            lines += ["", "[giftcard]", f"number = {_toml_str(number)}", f"pin = {_toml_str(pin)}"]

        if input(f"\nWrite {target}? [y/N] ").strip().lower() != "y":
            print("Aborted. Nothing written.")
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(target, 0o600)
        print(f"Written {target} (0600). Restart your MCP client to pick it up.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nAborted. Nothing written.")
        return 1
