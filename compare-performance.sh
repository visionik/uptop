#!/bin/bash
# Compare Python vs Mojo performance

cd "$(dirname "$0")"
export PYTHONPATH=src

echo "==================================="
echo "Performance Comparison: Python vs Mojo"
echo "==================================="
echo ""

echo "1️⃣  Python version (baseline):"
echo "   Collecting all processes (~1,500+)..."
time UPTOP_USE_MOJO=false .venv/bin/python -c "
import asyncio
from uptop.plugins.processes import ProcessCollector

async def test():
    collector = ProcessCollector(use_mojo=False)
    data = await collector.collect()
    print(f'   Collected: {len(data.processes)} processes')
    print(f'   Total count: {data.total_count}')

asyncio.run(test())
" 2>&1 | grep -v "INFO:"

echo ""
echo "2️⃣  Mojo version (optimized):"
echo "   Collecting top 100 processes only..."
time UPTOP_USE_MOJO=true .venv/bin/python -c "
import asyncio
from uptop.plugins.processes import ProcessCollector

async def test():
    collector = ProcessCollector(use_mojo=True, max_processes=100)
    data = await collector.collect()
    print(f'   Collected: {len(data.processes)} processes')
    print(f'   Total count: {data.total_count}')

asyncio.run(test())
" 2>&1 | grep -v "INFO:"

echo ""
echo "==================================="
echo "To run TUI with Mojo: ./run-mojo-tui.sh"
echo "==================================="
