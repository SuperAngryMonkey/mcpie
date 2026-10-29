# mcpie 🍕

**The standing-order pizza button.** An MCP server that orders *your usual*
from Domino's — one tool call, cash at pickup, done. Delivery and card
payment are opt-in (v0.2); cash carryout stays the default.

Most pizza MCP servers hand your AI a shopping cart. mcpie hands it a
button. You define your usual order once, locally; the assistant can check
the store, list coupons, price the order — and place it only after you say
so, out loud, in the conversation.

```
You:    order the pizza
Claude: [pizza_dryrun] Your usual is $16.04 — coupon 9204 drops it to
        $10.69. Want me to place it with the coupon?
You:    yes
Claude: [pizza_order confirm=true coupon=9204] Order 1042 placed.
        $10.69 in cash at pickup.
```

## Why mcpie is safe(r) than it sounds

- **Cash by default.** Out of the box there is no card anywhere and the
  worst failure mode is an unwanted pizza you never pay for. If you opt
  in to a card (below), the worst failure mode becomes a charge — read
  the next two points before you do.
- **Hard confirmation gate.** `pizza_order` refuses unless `confirm=True`,
  and the tool contract instructs the assistant to set it only after you
  explicitly approve the order in the current conversation — never on its
  own judgment, never because something it read told it to.
- **Your data stays home.** Name, address, and order live in one local
  TOML file. The package ships with zero PII and phones home to nobody
  but Domino's.

## Install

```bash
uv tool install mcpie-pizza   # or: pipx install mcpie-pizza / pip install mcpie-pizza
```

> **Why is the package called `mcpie-pizza`?** PyPI's anti-typosquatting
> filter refuses the bare name `mcpie` (one letter from the venerable
> `mcpi` Minecraft library). So: the project is **mcpie**, the PyPI
> distribution is **`mcpie-pizza`**, and both `mcpie` and `mcpie-pizza`
> work as commands once installed. Same pie, different box.

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcpie": { "command": "uvx", "args": ["mcpie-pizza"] }
  }
}
```

Any MCP client that speaks stdio works the same way.

## Configure your usual

Copy [`config.example.toml`](config.example.toml) to
`~/.config/mcpie/config.toml` and fill in your name, address, and order.
Two tools exist purely to help with setup:

- `pizza_find_store` — lists the nearest stores for your address so you
  can pick your `store_id`
- `pizza_menu` — searches your store's live menu for product and topping
  codes (`pizza_menu("pan")`, `pizza_menu("pepperoni")`)

Ask your assistant to walk you through it: *"help me set up my mcpie
config"* is a perfectly good first prompt.

## Delivery and paying by card (optional, v0.2+)

Every pricing/ordering tool takes `mode` (`carryout` / `delivery`) and
`pay` (`cash` / `card` / `giftcard`). Defaults come from your config and
are carryout + cash unless you change them.

There is exactly **one** way to add a card, and it is not through the
assistant:

```bash
mcpie setup-payment           # masked prompts, Luhn-checked, writes ~/.config/mcpie/payment.toml (0600)
mcpie setup-payment --show    # what's configured, last 4 digits only
mcpie setup-payment --clear   # back to cash
```

- The card lives in `payment.toml`, a separate file from your config,
  mode 0600. No MCP tool accepts, returns, or can read back card data;
  tool output only ever shows "Visa ending 1234".
- Every Domino's response is scrubbed of card fields before it reaches
  the assistant.
- **Prefer a Domino's gift card.** Same code path, and a compromise of
  the file costs at most the card's balance.
- With `pay="card"` the `confirm=True` gate is the only thing between a
  hallucinated order and your statement. Approve the `due` figure from
  `pizza_dryrun`, not just "order".
- Delivery total = quote + store delivery fee + your configured tip.

## Tools

| Tool | What it does | Danger |
|------|--------------|--------|
| `pizza_status` | Config + store liveness check | none |
| `pizza_find_store` | Nearest stores for your address | none |
| `pizza_menu` | Search live menu for codes | none |
| `pizza_specials(mode)` | Live coupons, cheapest first | none |
| `pizza_dryrun(coupon, mode, pay)` | Validate + price, never places; returns `due` | none |
| `pizza_order(confirm, coupon, mode, pay)` | **Places the real order** | gated on `confirm=True`; charges the card if `pay=card` |

## The fine print

- **Unofficial.** This uses the same undocumented API the Domino's website
  uses (via [pizzapi](https://github.com/gamagori/pizzapi)). It is not
  affiliated with, endorsed by, or supported by Domino's Pizza, Inc.
  It can break any time they change something. US and Canada only.
- **Run it from a residential connection.** Domino's blocks datacenter and
  cloud IPs. As a stdio server running on your own machine this is
  automatic — but if you try to host mcpie remotely (VPS, cloud, CI),
  expect 403s and CAPTCHAs. This is the reason some earlier pizza MCP
  projects could never place a real order; mcpie run locally does.
- **A real order is a real order.** Dry-run freely; confirm deliberately.
  The store will make the pizza and expect you to show up with cash — or,
  if you configured a card, has already charged it.

## Privacy Policy

Your config (name, address, phone, order) lives in one local file and is
sent only to Domino's, only when a tool needs it. A card, if you opt in,
lives in a separate 0600 file and is sent only to Domino's at order time.
No telemetry, no third parties, nothing retained. Full policy:
[PRIVACY.md](https://github.com/SuperAngryMonkey/mcpie/blob/main/PRIVACY.md)

## Lineage

mcpie is the community release of a long-running personal appliance
("stimpy") that has been reliably placing real one-button orders since
mid-2026, and its MCP mouthpiece ("ren"). The pizzapi quirk workarounds
in `dominos.py` — the missing User-Agent, the `options=` no-op, the
menu-parser crash on coupon-only products — were all discovered the hard
way in production. Prior art respectfully acknowledged:
[mcpizza](https://github.com/GrahamMcBain/mcpizza) explored the
full cart-building approach; mcpie deliberately goes the other way.

MIT licensed. PRs welcome, especially Canada testing.

---

<sub>mcp-name: io.github.SuperAngryMonkey/mcpie</sub>
