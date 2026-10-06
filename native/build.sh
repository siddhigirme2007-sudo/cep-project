#!/usr/bin/env bash
# Builds the native helpers used by modules/analysis.py and
# modules/extraction.py. Run once after cloning the project.
set -e
cd "$(dirname "$0")"

echo "Building classify (C)..."
gcc -O2 -Wall -Wextra -o classify classify.c

echo "Building parse_lines (C++)..."
g++ -O2 -std=c++17 -Wall -Wextra -o parse_lines parse_lines.cpp

echo "Done. Built: $(pwd)/classify and $(pwd)/parse_lines"
