# etrade-mcp

An MCP server providing LLMs access to E*TRADE brokerage and bank accounts for investment tracking and portfolio analysis.

## Overview

This MCP server enables AI assistants to access your E*TRADE account data in a read-only capacity, helping you:
- Track investment performance across accounts
- Analyze asset allocation and diversification
- Reconcile balances with budgeting tools like YNAB
- Get real-time quotes for securities
- Make informed investment decisions

**Important**: This server is designed for personal finance management and portfolio monitoring, not for active trading. All operations are read-only.

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Get E*TRADE API Credentials

You'll need to obtain API credentials from E*TRADE in two stages: **sandbox keys first** (for testing), then **production keys** (for real account access).

> **Important**: Sandbox and production use completely separate credentials. You cannot "promote" sandbox keys to production - you'll need to obtain production keys through a separate process.

#### Step 1: Get Sandbox Keys (Required First)

Sandbox keys let you test with simulated data before accessing your real accounts.

1. **Log into your E*TRADE account** at https://us.etrade.com
   - Don't have an account? You can create one for free

2. **Visit the Sandbox Key Generator**: https://us.etrade.com/etx/ris/apikey

3. **Select an account** to tie your API key to (any account works - the key will work with all your accounts)

4. **Choose "Create Key"** as the Operation Type

5. **Click "Get Sandbox Key"**

6. **Copy your credentials** - you'll receive:
   - **Consumer Key** (also called API Key)
   - **Consumer Secret** (also called Secret Key)

   **⚠️ IMPORTANT**: Treat these like passwords - never commit them to version control

7. **Test with sandbox first** to make sure everything works before using real data

#### Step 2: Get Production Keys (After Testing with Sandbox)

Once you've tested with sandbox and are ready for real account access:

1. **Navigate to the E*TRADE Developer Portal**: https://developer.etrade.com/getting-started

2. **Scroll to the bottom** of the Getting Started page to find:
   - "Here are some things you need to gain and maintain API access"

3. **Complete the API User Intent Survey**:
   - Click the "API USER INTENT SURVEY" link (or visit https://us.etrade.com/etx/ris/apisurvey/#/questionnaire)
   - Must be logged into your E*TRADE account
   - Explain your intended use (personal portfolio monitoring)

4. **Sign the API Developer Agreement**:
   - Click the "API AGREEMENT" link (or visit https://us.etrade.com/etx/ris/apisurvey/#/agreement)
   - Review and accept the agreement terms
   - This is an online form - no need to download or email anything

5. **Production keys provided immediately** after completing both forms
   - You'll receive a new **Consumer Key** and **Consumer Secret**
   - These are completely different from your sandbox credentials

**Requirements**:
- Active E*TRADE brokerage or bank account
- Completed User Intent Survey
- Signed API Developer Agreement

**Note**: This MCP server is read-only, so it's safe to use with production credentials.

### 3. Set Environment Variables

Using the credentials from Step 2, configure your environment variables.

**For sandbox testing** (start here):
```bash
export ETRADE_CONSUMER_KEY="your_sandbox_consumer_key_here"
export ETRADE_CONSUMER_SECRET="your_sandbox_consumer_secret_here"
export ETRADE_ENVIRONMENT="sandbox"
```

**For production** (real account data):
```bash
export ETRADE_CONSUMER_KEY="your_production_consumer_key_here"
export ETRADE_CONSUMER_SECRET="your_production_consumer_secret_here"
export ETRADE_ENVIRONMENT="production"
```

> **Critical**: The `ETRADE_ENVIRONMENT` must match the credentials you're using. Sandbox keys only work with `ETRADE_ENVIRONMENT="sandbox"` and production keys only work with `ETRADE_ENVIRONMENT="production"`. Mismatched environment/credentials will result in authentication errors.

**💡 Tip**: Create a `.env` file or add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.)

#### Multiple Profiles (Optional)

You can configure multiple E*TRADE profiles (e.g., for different family members or accounts):

```bash
# Default profile (profile 0)
export ETRADE_CONSUMER_KEY="primary_consumer_key"
export ETRADE_CONSUMER_SECRET="primary_consumer_secret"
export ETRADE_ENVIRONMENT="production"

# Additional profile (profile 1)
export ETRADE_CONSUMER_KEY_1="secondary_consumer_key"
export ETRADE_CONSUMER_SECRET_1="secondary_consumer_secret"
export ETRADE_ENVIRONMENT_1="production"
export ETRADE_PROFILE_LABEL_1="Spouse's Account"

# Profile 2, etc.
export ETRADE_CONSUMER_KEY_2="another_consumer_key"
export ETRADE_CONSUMER_SECRET_2="another_consumer_secret"
export ETRADE_ENVIRONMENT_2="sandbox"
export ETRADE_PROFILE_LABEL_2="Testing"
```

Each profile can access different E*TRADE accounts with separate credentials. The MCP server will automatically detect and use all configured profiles.

### 4. Run the Server

```bash
uv run python server.py
```

### 5. Complete OAuth Authorization

When you start the server for the first time (or when tokens expire), you'll need to authorize access.

The MCP server will automatically open a browser window with a local authorization page.

**Authorization Steps**:

1. **Click "Open E*TRADE Authorization Page"** - this takes you to E*TRADE's website
2. **Log into E*TRADE** and review the permissions (read-only access)
3. **E*TRADE displays a verification code** - copy it
4. **Paste the code** into the form on the authorization page
5. **Click "Submit Code"** - the server completes authorization automatically

**Token Persistence**: After initial authorization, the server saves your access tokens securely in `~/.config/etrade-mcp/`. Tokens are automatically renewed when they expire, so you typically won't need to re-authorize unless:
- Tokens are manually deleted
- You're switching between sandbox and production environments
- E*TRADE invalidates the tokens (rare)

**Multi-Profile**: Each profile maintains its own tokens and authorization state independently.

> **Note**: The authorization page is served by your local MCP server (not E*TRADE). This web-based flow is designed to work seamlessly with MCP clients like Claude Desktop.

## Available Tools

### `list_accounts()`
Returns all active E*TRADE accounts (brokerage and bank).

**Example**:
```python
list_accounts()
```

**Returns**: List of accounts with:
- Account ID and encrypted key
- Account description/nickname
- Account type (INDIVIDUAL, JOINT, IRA, etc.)
- Account mode (CASH, MARGIN, IRA)
- Institution type (BROKERAGE or BANK)

### `get_account_balance(account_id_key)`
Get detailed balance information for a specific account.

**Args**:
- `account_id_key`: Account identifier from `list_accounts()` response

**Example**:
```python
get_account_balance("abc123xyz")
```

**Returns**: Balance details including:
- Cash balances and buying power
- Total account value
- Margin information (for margin accounts)
- Pending deposits and holds

### `get_account_portfolio(account_id_key)`
Get all holdings/positions for a specific account.

**Args**:
- `account_id_key`: Account identifier from `list_accounts()` response

**Example**:
```python
get_account_portfolio("abc123xyz")
```

**Returns**: Portfolio with:
- All positions (stocks, bonds, funds, etc.)
- Security symbols and descriptions
- Quantity, cost basis, and current market value
- Gains/losses (total and daily)
- Total portfolio market value

### `get_quotes(symbols)`
Get real-time or delayed quotes for securities.

**Args**:
- `symbols`: List of ticker symbols (max 25 per request)

**Example**:
```python
get_quotes(["AAPL", "MSFT", "SPY"])
```

**Returns**: Quotes with:
- Current pricing (last trade, bid, ask)
- Price changes (dollar and percentage)
- Trading volume
- Price ranges (daily and 52-week)
- Fundamental data (P/E ratio, dividend, market cap)

## Common Use Cases

### Check Portfolio Performance
```
"How are my investments doing today?"
```
The AI will use `list_accounts()` and `get_account_portfolio()` for each account to analyze performance.

### Reconcile with YNAB
```
"Do my E*TRADE balances match YNAB?"
```
The AI will use `get_account_balance()` to compare against YNAB account balances.

### Analyze Asset Allocation
```
"What's my stock to bond ratio?"
```
The AI will fetch all portfolios and categorize holdings by asset class.

### Get Quick Quotes
```
"What's Apple trading at right now?"
```
The AI will use `get_quotes(["AAPL"])` to get current pricing.

## Security Notes

### Credential Security
- **Never commit credentials to version control**
- Store `ETRADE_CONSUMER_KEY` and `ETRADE_CONSUMER_SECRET` in environment variables or secure credential stores
- These credentials provide read-only access to your financial accounts
- Treat them like passwords

### OAuth Flow
- Authorization is required on first use and when tokens expire
- Access tokens are securely stored in `~/.config/etrade-mcp/` and automatically renewed
- Tokens are stored separately per profile and environment (sandbox vs. production)
- Verification codes are single-use and expire after 5 minutes
- Web-based OAuth flow works seamlessly with MCP clients (Claude Desktop, etc.)

### Read-Only Access
- This server only performs read operations
- No trading, transfers, or account modifications are possible
- Safe to use with production accounts
- Review E*TRADE's API documentation for full details on permissions

## Sandbox vs. Production

### Sandbox Environment
- **Purpose**: Testing and development
- **Account Required**: No real E*TRADE account needed
- **Data**: Simulated account data
- **Risk**: Zero (no real money)
- **Use When**: Learning the API, testing integrations, developing features

### Production Environment
- **Purpose**: Real account access
- **Account Required**: Active E*TRADE brokerage account
- **Data**: Your real investment accounts
- **Risk**: Low (read-only, but real credentials)
- **Use When**: Actual portfolio monitoring and analysis

**Recommendation**: Start with sandbox to test everything, then switch to production once comfortable.

## Troubleshooting

### "Failed to get request token"
- Verify your consumer key and secret are correct
- Check that you're using the right credentials for your environment (sandbox vs. production)
- Ensure your E*TRADE developer application is active

### "Failed to get access token"
- Verification code may have expired (they're only valid for 5 minutes)
- Restart the authorization flow
- Make sure you copied the entire verification code

### "Not authorized" error
- Tokens may have expired or been deleted
- The server will automatically prompt for re-authorization
- Complete the web-based OAuth flow when prompted

### No accounts returned
- In sandbox: This is expected if no sandbox data is available
- In production: Verify your E*TRADE account has active brokerage or bank accounts

### Quotes showing delayed data
- Quote delay depends on your E*TRADE account type and exchange
- Real-time quotes require appropriate account level and exchange agreements
- Delayed quotes are typically 15 minutes behind

## Development

### Running Tests
```bash
uv run pytest
```

### Type Checking
```bash
uv run mypy .
```

### Code Formatting
```bash
uv run ruff check .
```

## License

This is personal software for individual use. See your E*TRADE API agreement for terms of use regarding API access.

## Support

For E*TRADE API issues:
- E*TRADE Developer Portal: https://developer.etrade.com
- API Documentation: https://apisb.etrade.com/docs/api/account/api-account-v1.html

For MCP server issues:
- Review DESIGN.md for architecture and use cases
- Check that environment variables are set correctly
- Verify OAuth flow completes successfully
