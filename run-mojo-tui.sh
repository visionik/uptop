#!/bin/bash
# Launch uptop TUI with Mojo optimization enabled

cd "$(dirname "$0")"

export UPTOP_USE_MOJO=true
export PYTHONPATH=src

echo "🚀 Starting uptop with Mojo optimization..."
echo "   Max processes: 100 (vs ~1,500+ in Python)"
echo "   Expected speedup: 10-50x on process collection"
echo ""

.venv/bin/python -m uptop.cli tui
