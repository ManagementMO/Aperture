#!/bin/bash
# Hackathon demo recording script
# Run: bash scripts/record_demo.sh

set -e

echo "🔭 APERTURE — Context Engineering for Composio"
echo "Hackathon Demo Recording"
echo ""

cd "$(dirname "$0")/.."

echo "=========================================="
echo "DEMO 1: The Problem — Vanilla Composio"
echo "=========================================="
echo ""
echo "Reading 10,000 rows from Google Sheets..."
echo ""
uv run python -c "
import os
from composio import Composio
from aperture.tokenization import count_tokens

def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Set {name} before running the live demo.')
    return value

c = Composio(api_key=required('COMPOSIO_API_KEY'))
session = c.create(
    user_id=required('COMPOSIO_USER_ID'),
    toolkits=['googlesheets'],
    connected_accounts={'googlesheets': required('COMPOSIO_GOOGLESHEETS_CONNECTED_ACCOUNT_ID')},
)
resp = session.execute(
    tool_slug='GOOGLESHEETS_BATCH_GET',
    arguments={
        'spreadsheet_id': '1eyr5XV1pGyJTbRWpFVIp_fcrLK-oEp4tlVg3l1VsqR0',
        'sheet_name': 'Sheet1',
        'ranges': ['Sheet1!A1:M10001'],
    },
)
d = resp if isinstance(resp, dict) else resp.model_dump()
values = d.get('data', {}).get('valueRanges', [{}])[0].get('values', [])
tokens = count_tokens(values).tokens
print(f'Rows: {len(values):,}')
print(f'Tokens: {tokens:,}')
print(f'Context window: {tokens/128000*100:.0f}% of 128K limit')
print('')
print('❌ This single tool call EXCEEDS the context window!')
"

echo ""
echo "=========================================="
echo "DEMO 2: Aperture Compression"
echo "=========================================="
echo ""
uv run python scripts/honest_comparison.py

echo ""
echo "=========================================="
echo "DEMO 3: Agent Workflow"
echo "=========================================="
echo ""
uv run python scripts/demo.py --scenario research_project --mode auto --cache

echo ""
echo "=========================================="
echo "DEMO 4: Benchmarks"
echo "=========================================="
echo ""
uv run python scripts/benchmark.py --scenario research_project --mode auto

echo ""
echo "=========================================="
echo "DEMO 5: Dynamic Agent"
echo "=========================================="
echo ""
uv run python scripts/dynamic_agent_demo.py --intent "Find all open bugs in composio"

echo ""
echo "=========================================="
echo "Demo Complete!"
echo "=========================================="
echo ""
echo "Dashboard: uv run streamlit run dashboard/app.py"
