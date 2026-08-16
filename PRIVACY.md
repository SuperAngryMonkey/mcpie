# mcpie Privacy Policy

**The short version: your data lives on your machine and is sent to exactly
one place — Domino's — and only when you use a tool that needs it.**

## What mcpie stores

Your name, phone number, email, address, and standing order live in a single
local TOML file (default `~/.config/mcpie/config.toml`) that **you** create.
mcpie never writes it anywhere else, never uploads it, and the file is
excluded from the source repository by design.

## Where data goes

When you invoke a tool, mcpie communicates **only** with Domino's ordering
API (`order.dominos.com` / `order.dominos.ca`) — the same endpoints the
Domino's website uses:

- `pizza_status`, `pizza_menu`, `pizza_specials`, `pizza_find_store` send
  your store ID and/or address to Domino's to fetch store, menu, and coupon
  data. They are read-only.
- `pizza_dryrun` and `pizza_order` send your name, phone, email, address,
  and order contents to Domino's to price or place an order — exactly the
  information a checkout form would send.

## What mcpie never does

- **No card data, ever.** Payment is cash at pickup/delivery. There is no
  code path that accepts, stores, or transmits payment card information.
- **No telemetry, analytics, or tracking.** mcpie phones home to nobody.
  The author receives no data of any kind from your use of it.
- **No third parties.** No service other than Domino's ever receives your
  information.

## Your AI assistant

mcpie is an MCP server: tool inputs and outputs pass through whatever AI
client you connect it to (e.g. Claude). Store data, prices, and order
confirmations returned by tools are visible to that client, subject to its
own privacy policy. Your config file itself is never returned by any tool.

## Contact

Questions or concerns: open an issue at
https://github.com/SuperAngryMonkey/mcpie/issues
