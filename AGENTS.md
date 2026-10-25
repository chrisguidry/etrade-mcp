# Claude Instructions for E*TRADE MCP Server

## Testing

**CRITICAL**: This project requires 100% test coverage. This is inviolable.

- All new code must have corresponding tests
- Coverage target is 100% for all non-excluded code
- Use `pragma: no cover` only for truly untestable code (interactive OAuth flows, main blocks)
- Run tests with `uv run pytest` before committing
