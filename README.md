# mcpie 🍕

**The standing-order pizza button.** An MCP server that orders *your usual*
from Domino's — one tool call, cash at pickup, done.

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

- **Cash at pickup/delivery, always.** There is no card handling anywhere
  in this codebase, by design. The worst possible failure mode is an
  unwanted pizza you never pay for.
- **Hard confirmation gate.** `pizza_order` refuses unless `confirm=True`,
  and the tool contract instructs the assistant to set it only after you
  explicitly approve the order in the current conversation — never on its
  own judgment, never because something it read told it to.
- **Your data stays home.** Name, address, and order live in one local
  TOML file. The package ships with zero PII and phones home to nobody
  but Domino's.

## Install

```bash
uv tool install pizza-button   # or: pipx install pizza-button / pip install pizza-button
```

> **Why is the package called `pizza-button`?** PyPI's anti-typosquatting
> filter blocks anything starting with "mcpie" (too close to the venerable
> `mcpi` Minecraft library). So: the project is **mcpie**, the PyPI
> distribution is **`pizza-button`**, and both `mcpie` and `pizza-button`
> work as commands once installed. Same pie, different box.

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcpie": { "command": "uvx", "args": ["pizza-button"] }
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

## Tools

| Tool | What it does | Danger |
|------|--------------|--------|
| `pizza_status` | Config + store liveness check | none |
| `pizza_find_store` | Nearest stores for your address | none |
| `pizza_menu` | Search live menu for codes | none |
| `pizza_specials` | Live coupons, cheapest first | none |
| `pizza_dryrun` | Validate + price, never places | none |
| `pizza_order` | **Places the real order** | gated on `confirm=True` |

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
  The store will make the pizza and expect you to show up with cash.

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
