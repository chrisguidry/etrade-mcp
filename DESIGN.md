# DESIGN.md

This document outlines the driving use cases and design philosophy for the E*TRADE MCP Server, focused on helping individuals track their investment portfolios and make informed financial decisions.

## Division of Responsibilities

**MCP Server provides**:
- Structured access to E*TRADE account data with consistent formatting
- Clean abstractions over E*TRADE's OAuth and API complexity
- Efficient data retrieval without unnecessary token overhead
- Read-only operations focused on monitoring and analysis

**LLM provides**:
- Natural language understanding of investment questions
- Portfolio analysis and performance insights
- Comparison across accounts and asset classes
- Actionable recommendations based on user goals
- Integration with budgeting tools like YNAB

## Use Case Format Guide

Each use case follows this structure:
- **User says**: Natural language examples
- **Why it matters**: User context and needs
- **MCP Server Role**: Which tools to use and what data they provide
- **LLM Role**: Analysis and intelligence needed
- **Example Implementation Flow**: Step-by-step approach (when helpful)

## Core Use Cases

### 1. Portfolio Performance Check-ins

**User says**: "How are my investments doing?" or "What's my portfolio worth today?"

**Why it matters**: Individuals want quick snapshots of their investment performance without logging into E*TRADE. They need conversational summaries that highlight overall performance and significant changes.

**MCP Server Role**:
- `list_accounts()` - Get all brokerage accounts
- `get_account_portfolio(account_id_key)` - Get holdings for each account
- Returns positions with current market values, cost basis, and gains/losses

**LLM Role**:
- Aggregates performance across all accounts
- Calculates total portfolio value and overall gains
- Highlights best and worst performers
- Identifies significant changes from previous checks
- Generates conversational summary with key insights

**Example Implementation Flow**:
1. Call `list_accounts()` to get all brokerage accounts
2. For each account, call `get_account_portfolio(account_id_key)`
3. Aggregate all positions across accounts
4. Calculate totals: market value, total gains, percentage returns
5. Identify top gainers/losers by dollar amount and percentage
6. Format as natural language response

### 2. Account Balance Reconciliation

**User says**: "Does my E*TRADE balance match what's in YNAB?" or "What's my total liquid assets?"

**Why it matters**: Users who track finances in YNAB or other tools need to verify that their investment account balances are correctly reflected. They want to catch discrepancies early.

**MCP Server Role**:
- `list_accounts()` - Get all accounts (including bank accounts)
- `get_account_balance(account_id_key)` - Get precise balance for each account
- Returns cash balances, total account values, and buying power

**LLM Role**:
- Compares E*TRADE balances with YNAB account balances
- Identifies discrepancies and suggests reasons (pending transactions, timing)
- Calculates total liquid assets across all accounts
- Provides reconciliation guidance

**Future MCP Tools Needed**:
- Integration with YNAB MCP server to fetch YNAB balances directly

### 3. Asset Allocation Analysis

**User says**: "What's my stock to bond ratio?" or "Am I too heavily invested in tech stocks?"

**Why it matters**: Diversification is critical for risk management. Users need to understand their exposure across asset classes, sectors, and individual securities without manual calculation.

**MCP Server Role**:
- `list_accounts()` - Get all accounts
- `get_account_portfolio(account_id_key)` - Get all holdings
- Returns security types, market values, and descriptions

**LLM Role**:
- Categorizes holdings by asset class (stocks, bonds, cash, etc.)
- Groups by sector for equity holdings
- Calculates allocation percentages
- Compares to target allocations or best practices
- Identifies concentration risks (e.g., >10% in single stock)
- Suggests rebalancing if needed

**Example Implementation Flow**:
1. Fetch all portfolios across accounts
2. Categorize each position by asset class using security type and symbol
3. Calculate market value totals per category
4. Compute percentages of total portfolio
5. Identify concentrations and outliers
6. Generate allocation summary with recommendations

### 4. Individual Security Deep Dive

**User says**: "Tell me about my Apple holdings" or "How is Microsoft performing in my portfolio?"

**Why it matters**: Users want to understand individual security performance across all accounts, especially for significant holdings. They may own the same security in multiple accounts (401k, IRA, taxable).

**MCP Server Role**:
- `list_accounts()` - Get all accounts
- `get_account_portfolio(account_id_key)` - Get holdings from all accounts
- `get_quotes([symbol])` - Get current quote for the security
- Returns positions across accounts and real-time market data

**LLM Role**:
- Aggregates all positions in the specific security
- Calculates total shares, average cost basis, total market value
- Compares cost basis to current price
- Analyzes gain/loss (total and unrealized)
- Provides current market context (quote data)
- Highlights any significant changes or news implications

### 5. Pre-Rebalancing Planning

**User says**: "I have $5,000 to invest, where should it go?" or "What should I buy to rebalance toward 60/40?"

**Why it matters**: Users making new contributions or rebalancing need to understand their current allocation to make informed investment decisions.

**MCP Server Role**:
- `list_accounts()` - Get accounts to determine where funds can be invested
- `get_account_portfolio(account_id_key)` - Current holdings
- `get_account_balance(account_id_key)` - Available cash for investment
- Returns current allocation and available funds

**LLM Role**:
- Calculates current asset allocation
- Determines what to buy to reach target allocation
- Considers available cash in each account
- Suggests specific securities or categories to purchase
- Factors in account type (taxable vs. tax-advantaged) for tax efficiency

### 6. Quick Quote Checks

**User says**: "What's Apple trading at?" or "Get me quotes for my top 5 holdings"

**Why it matters**: Users want quick price checks without navigating to financial websites or apps. They may want to check on specific securities before making decisions.

**MCP Server Role**:
- `get_quotes(symbols)` - Get real-time or delayed quotes
- Returns current prices, changes, volume, and fundamental data

**LLM Role**:
- Formats quote data conversationally
- Highlights significant price movements
- Provides context (52-week range, P/E ratio, dividend yield)
- Relates quote to user's holdings if applicable

**Example Implementation Flow**:
1. User requests quote(s) by name or symbol
2. Convert names to symbols if needed
3. Call `get_quotes([symbols])`
4. Format response highlighting key metrics
5. Add context like "This is up 5% today" or "Near 52-week high"

### 7. Cash Management

**User says**: "How much cash do I have available to invest?" or "What's my buying power?"

**Why it matters**: Before making investment decisions, users need to know how much cash they have available across accounts, including both settled cash and margin buying power (if applicable).

**MCP Server Role**:
- `list_accounts()` - Get all accounts
- `get_account_balance(account_id_key)` - Get balance details
- Returns cash balances, buying power, and pending holds

**LLM Role**:
- Aggregates available cash across all accounts
- Distinguishes between cash balance and buying power
- Warns about uncleared deposits or holds
- Suggests optimal account for deployment based on goals

### 8. Portfolio Comparison Over Time

**User says**: "How has my portfolio changed since last month?" or "Am I making progress toward my goals?"

**Why it matters**: Users want to track progress over time to ensure they're on track for retirement or other financial goals. They need historical context, not just current snapshots.

**MCP Server Role**:
- `list_accounts()` - Current accounts
- `get_account_portfolio(account_id_key)` - Current holdings and performance
- Returns current state with embedded gain/loss data

**LLM Role**:
- Uses available performance data (days_gain, total_gain)
- Compares to previous checks if cached/stored
- Analyzes trends in allocation shifts
- Relates performance to broader market indices
- Provides progress assessment toward goals

**Future MCP Tools Needed**:
- Historical portfolio snapshots or time-series data
- Performance comparison to benchmarks

### 9. Tax-Aware Investment Insights

**User says**: "Which accounts should I sell from for tax efficiency?" or "Show me my taxable vs. tax-advantaged holdings"

**Why it matters**: Tax efficiency is critical for long-term wealth building. Users need to understand which accounts hold which assets and make tax-smart decisions about where to buy, sell, or hold securities.

**MCP Server Role**:
- `list_accounts()` - Get accounts with account types (IRA, Individual, etc.)
- `get_account_portfolio(account_id_key)` - Holdings by account
- Returns positions with account type context

**LLM Role**:
- Categorizes accounts by tax treatment (taxable, tax-deferred, tax-free)
- Analyzes holdings in each category
- Identifies tax-inefficient placements (e.g., bonds in taxable accounts)
- Suggests improvements: "Move bonds to IRA, keep stocks in taxable"
- Considers tax implications of potential sales

**Future Enhancements**:
- Cost basis tracking per tax lot
- Estimated tax impact calculations

## Design Principles for Use Cases

1. **Read-Only Focus**: All tools are read-only. No order placement, transfers, or account modifications
2. **Token Efficiency**: Separate tools for list/detail patterns. Users get summaries first, then drill down
3. **Account-Centric**: Most detailed operations require an account_id_key to avoid over-fetching
4. **Batch When Possible**: Quote tool accepts multiple symbols (up to 25) to reduce API calls
5. **Conversational First**: Responses should sound natural, not like raw API data
6. **Privacy Aware**: Server is designed for single-user or household deployment with separate OAuth tokens per profile
7. **Multi-Profile Support**: Multiple E*TRADE accounts (e.g., different family members) can be accessed simultaneously

## Tool Implementation Status

### Currently Implemented (4 tools)
- ✅ `list_accounts()` - Get all active accounts
- ✅ `get_account_balance(account_id_key)` - Detailed balance for one account
- ✅ `get_account_portfolio(account_id_key)` - Holdings for one account
- ✅ `get_quotes(symbols)` - Quotes for up to 25 securities

### Potential Future Tools
- 🔄 `get_transactions(account_id_key)` - Recent transactions for reconciliation
- 🔄 `get_option_chains(symbol)` - Option chain data for options analysis
- 🔄 `get_market_hours()` - Market open/close status

### Won't Implement (Out of Scope)
- ❌ Order placement or trading operations
- ❌ Complex options analytics (Greeks, probability analysis)
- ❌ Technical analysis indicators
- ❌ Real-time streaming quotes
- ❌ Historical charts or time-series data (except what's in quotes)

## Authentication Model

E*TRADE uses OAuth 1.0 with a manual authorization step:

1. **One-time setup** (developer.etrade.com):
   - User registers an application
   - Receives Consumer Key and Consumer Secret
   - Sets callback to "oob" (out-of-band)

2. **Per-session authorization**:
   - Server starts and prompts for OAuth authorization
   - Opens browser for user to log into E*TRADE
   - User authorizes and receives verification code
   - User enters code in terminal
   - Session established for duration of server run

3. **Security considerations**:
   - Consumer credentials stored in environment variables
   - Access tokens are session-only (not persisted)
   - Single-user model (no multi-tenant concerns)
   - Works with both sandbox (testing) and production

## Success Metrics

A use case is successful when:
- It saves the user time vs. using E*TRADE website directly
- It enables insights not easily visible in E*TRADE's interface
- It integrates investment data with other financial tools (YNAB, budgeting)
- It helps users make better investment decisions through clear analysis
- It respects token economy and doesn't waste context on unnecessary data
