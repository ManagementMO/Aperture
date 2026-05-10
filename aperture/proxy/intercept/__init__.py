"""Per-meta-tool interception handlers.

The router dispatches inbound MCP `tools/call` requests by meta-tool slug
into one of these handlers. Each handler decides cache / overlay / tokenize
behavior based on Plan-Agent 1 §3's decision matrix.
"""
