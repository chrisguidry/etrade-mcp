# etrade-mcp

An MCP server that gives AI assistants read-only access to your E\*TRADE accounts for portfolio monitoring and investment analysis.

## What It Does

Ask your AI assistant questions like:

- "How are my investments performing today?"
- "What's my current asset allocation?"
- "Do my E\*TRADE balances match what's in [YNAB](https://github.com/chrisguidry/you-need-an-mcp)?"
- "What's the current price of Apple stock?"
- "What dividends did I get last month?"

The server has seven tools, and every one of them only reads:

- `list_profiles`: the E\*TRADE logins the server is configured for
- `list_accounts`: the open accounts for one profile
- `get_account_balance`: one account's cash, buying power, and total value
- `get_account_portfolio`: the positions in one account, with their value and gains
- `get_transactions`: the trades, dividends, and transfers in one brokerage account over a date range
- `get_transaction`: one transaction, with its category, memo, check number, order number, and settlement date
- `get_quotes`: quotes for up to 25 symbols

None of them places, changes, or cancels an order, or moves money.

## Setup

### 1. Install

```bash
uv sync
```

### 2. Get E\*TRADE API Credentials

You'll need API credentials from E\*TRADE. Start with sandbox (for testing), then move to production (for real data).

#### Sandbox Keys (Testing)

1. Log into E\*TRADE at https://us.etrade.com
2. Visit https://us.etrade.com/etx/ris/apikey
3. Select any account, choose "Create Key", click "Get Sandbox Key"
4. Copy your Consumer Key and Consumer Secret

#### Production Keys (Real Accounts)

1. Go to https://developer.etrade.com/getting-started
2. Scroll to the bottom and complete:
   - API User Intent Survey: https://us.etrade.com/etx/ris/apisurvey/#/questionnaire
   - API Developer Agreement: https://us.etrade.com/etx/ris/apisurvey/#/agreement
3. You'll immediately receive production Consumer Key and Consumer Secret

### 3. Configure Environment Variables

**For sandbox:**

```bash
export ETRADE_0_CONSUMER_KEY="your_sandbox_consumer_key"
export ETRADE_0_CONSUMER_SECRET="your_sandbox_consumer_secret"
export ETRADE_0_ENVIRONMENT="sandbox"
```

**For production:**

```bash
export ETRADE_0_CONSUMER_KEY="your_production_consumer_key"
export ETRADE_0_CONSUMER_SECRET="your_production_consumer_secret"
export ETRADE_0_ENVIRONMENT="production"
```

**Multiple profiles** (optional, for family members or separate accounts):

```bash
# Profile 0 (can use legacy ETRADE_CONSUMER_KEY or ETRADE_0_CONSUMER_KEY)
export ETRADE_0_CONSUMER_KEY="primary_key"
export ETRADE_0_CONSUMER_SECRET="primary_secret"
export ETRADE_0_ENVIRONMENT="production"

# Profile 1
export ETRADE_1_CONSUMER_KEY="secondary_key"
export ETRADE_1_CONSUMER_SECRET="secondary_secret"
export ETRADE_1_ENVIRONMENT="production"
export ETRADE_1_LABEL="Spouse's Account"

# Profile 2
export ETRADE_2_CONSUMER_KEY="another_key"
export ETRADE_2_CONSUMER_SECRET="another_secret"
export ETRADE_2_ENVIRONMENT="sandbox"
export ETRADE_2_LABEL="Testing"
```

**Important**: Never commit credentials to version control. The `ETRADE_N_ENVIRONMENT` must match your credentials: sandbox keys only work with `sandbox`, production keys only work with `production`.

### 4. Run and Authorize

```bash
uv run etrade-mcp
```

On first run (or when tokens expire), the server opens a browser to authorize access:

1. Click "Open E\*TRADE Authorization Page"
2. Log into E\*TRADE and copy the verification code
3. Paste the code and click "Submit Code"

Tokens are saved in `~/.config/etrade-mcp/` and automatically renewed. Each profile maintains separate tokens.

E\*TRADE expires every token at midnight US Eastern time. After that, or when E\*TRADE stops accepting a profile's token, the next tool call for that profile opens the authorization page in a browser again. When an MCP client starts the server with `fastmcp run src/etrade_mcp/server.py:mcp` and no token is saved, the first tool call opens the same page.

## Development

```bash
uv sync
uv run pytest               # requires 100% branch coverage
uv run prek run --all-files # lint, format, spelling, type-check, file-size limits
```

The hooks run with [prek](https://github.com/j178/prek), which reads `.pre-commit-config.yaml`. Run `uv run prek install` once to run them on every commit. They run ruff, codespell, [loq](https://github.com/jakekaplan/loq) for a 500-line limit on each file, and pyright in strict mode on the package and the tests.

CI runs the tests and every hook on every push to `main` and on every pull request.

## Resources

- E\*TRADE Developer Portal: https://developer.etrade.com
- API Documentation: https://apisb.etrade.com/docs/api/account/api-account-v1.html
- Architecture details: See DESIGN.md
