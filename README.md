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

Before you can use this MCP server, you need to obtain `consumer_key` and `consumer_secret` from E*TRADE:

#### Step-by-Step:

1. **Go to https://developer.etrade.com**

2. **Log in** with your E*TRADE credentials
   - If you don't have an E*TRADE account, you can still create a developer account for sandbox testing
   - Production account registration: https://us.etrade.com

3. **Navigate to "My Apps"** (or similar menu option)

4. **Click "Create New App"** or "Register Application"

5. **Fill in the application registration form:**
   - **Application Name**: `Personal MCP Server` (or any name you prefer)
   - **Description**: `Personal finance AI assistant integration`
   - **Callback URL**: `oob` (stands for "out-of-band" - **required** for desktop applications)

6. **Submit the registration**

7. **Copy your credentials** - you'll receive two sets of keys:

   **Sandbox Keys** (for testing with simulated data):
   - Consumer Key (also called API Key)
   - Consumer Secret (also called Secret Key)

   **Production Keys** (for accessing real account data):
   - Consumer Key
   - Consumer Secret

   **⚠️ IMPORTANT**: Treat these like passwords - never commit them to version control

8. **Start with sandbox for testing:**
   - You can use sandbox without a real E*TRADE brokerage account
   - Provides simulated data for development and testing
   - No risk to real money or accounts

9. **Switch to production when ready:**
   - Requires an active E*TRADE brokerage account
   - Provides access to your real account data
   - This server is read-only, so it's safe to use with production credentials

### 3. Set Environment Variables

Using the credentials from step 2, set these environment variables:

**For sandbox testing** (recommended to start):
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

When you start the server for the first time, you'll need to authorize access:

1. The server will automatically open a browser window with an authorization page
2. Click the link to authorize with E*TRADE
3. Log into E*TRADE on the authorization page
4. Review and accept the permissions (read-only access)
5. E*TRADE will display a **verification code**
6. Copy the verification code and paste it into the form on the authorization page
7. Click "Submit Code"
8. The server will complete authorization and start running

**Token Persistence**: After initial authorization, the server saves your access tokens securely in `~/.config/etrade-mcp/`. Tokens are automatically renewed when they expire, so you typically won't need to re-authorize unless:
- Tokens are manually deleted
- You're switching between sandbox and production
- E*TRADE invalidates the tokens (rare)

**Multi-Profile**: Each profile maintains its own tokens and authorization state independently.

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
