# mcpie Privacy Policy

**The short version: your data lives on your machine and is sent to exactly
one place — Domino's — and only when you use a tool that needs it. Card
data is opt-in, lives in its own 0600 file, and is never visible to the
assistant.**

## What mcpie stores

Your name, phone number, email, address, and standing order live in a single
local TOML file (default `~/.config/mcpie/config.toml`) that **you** create.
mcpie never writes it anywhere else, never uploads it, and the file is
excluded from the source repository by design.

## Payment data (optional, v0.2+)

mcpie is cash-only unless you run `mcpie setup-payment` in a terminal.
That command writes `payment.toml` (default `~/.config/mcpie/payment.toml`,
file mode 0600) containing a credit card or Domino's gift card. Then:

- The file is read only when `pay="card"` / `pay="giftcard"` is used, and
  its contents are sent only to Domino's in the order request.
- No MCP tool accepts card details as input, and no tool returns them:
  Domino's responses are scrubbed of card fields before leaving mcpie,
  and tool output shows at most the card type and last four digits.
- `mcpie setup-payment --clear` deletes the file.

## Where data goes

When you invoke a tool, mcpie communicates **only** with Domino's ordering
API (`order.dominos.com` / `order.dominos.ca`) — the same endpoints the
Domino's website uses:

- `pizza_status`, `pizza_menu`, `pizza_specials`, `pizza_find_store` send
  your store ID and/or address to Domino's to fetch store, menu, and coupon
  data. They are read-only.
- `pizza_dryrun` and `pizza_order` send your name, phone, email, address,
  and order contents to Domino's to price or place an order — exactly the
  information a checkout form would send. With card or gift-card payment
  configured and selected, `pizza_order` also sends that payment, as a
  checkout form would.

## What mcpie never does

- **No card data through the assistant, ever.** Payment is cash unless
  you opt in via the terminal; even then no tool input or output carries
  a card number, and the card never leaves your machine except to Domino's.
- **No telemetry, analytics, or tracking.** mcpie phones home to nobody.
  The author receives no data of any kind from your use of it.
- **No third parties.** No service other than Domino's ever receives your
  information.

## Your AI assistant

mcpie is an MCP server: tool inputs and outputs pass through whatever AI
client you connect it to (e.g. Claude). Store data, prices, and order
confirmations returned by tools are visible to that client, subject to its
own privacy policy. Your config file itself is never returned by any tool.

## Data retention

mcpie retains nothing. There is no database, no log file, and no persistent
state: the only runtime memory is the last order's ID, amount, mode and
payment label (e.g. "Visa ending 1234"), held in process memory and gone
when the server stops. Your config and payment files persist only because
you created them, and deleting them removes everything. Domino's
retains order data under its own privacy policy, as with any order placed
through its website.

## Contact

Questions or concerns: open an issue at
https://github.com/SuperAngryMonkey/mcpie/issues
