#!/usr/bin/env python3
"""Text chunking utility for RLM-style context decomposition.

Usage:
    chunk_text.py info <file>                        Print context assessment as JSON
    chunk_text.py chunk <file> [--size N] [--overlap N]  Chunk file into pieces
    chunk_text.py boundaries <file>                  Detect natural boundaries

Options:
    --size CHARS      Target chunk size in characters (default: 100000)
    --overlap CHARS   Overlap between chunks (default: 500)
"""

import json
import os
import re
import sys


def cmd_info(path):
    """Print context assessment for a file."""
    stat = os.stat(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    char_count = len(content)
    estimated_tokens = char_count // 4
    target_chunk_chars = 100_000
    suggested_chunks = max(1, (char_count + target_chunk_chars - 1) // target_chunk_chars)

    # Detect structure
    has_markdown_headers = bool(re.search(r"^#{1,6}\s", content, re.MULTILINE))
    has_python_defs = bool(re.search(r"^(def |class )", content, re.MULTILINE))
    has_structure = has_markdown_headers or has_python_defs

    info = {
        "file": path,
        "file_size_bytes": stat.st_size,
        "line_count": line_count,
        "char_count": char_count,
        "estimated_tokens": estimated_tokens,
        "suggested_chunks": suggested_chunks,
        "has_structure": has_structure,
        "structure_types": [],
    }
    if has_markdown_headers:
        info["structure_types"].append("markdown_headers")
    if has_python_defs:
        info["structure_types"].append("python_defs")

    json.dump(info, sys.stdout, indent=2)
    print()


def cmd_chunk(path, size=100_000, overlap=500):
    """Split file into chunks, breaking at natural boundaries when possible."""
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content) <= size:
        chunks = [{"index": 0, "start_char": 0, "end_char": len(content),
                    "char_count": len(content), "content": content}]
        json.dump(chunks, sys.stdout, indent=2)
        print()
        return

    chunks = []
    pos = 0
    index = 0

    while pos < len(content):
        end = min(pos + size, len(content))

        # If not at the end of file, try to break at a natural boundary
        if end < len(content):
            # Look backward from end for a good break point
            search_start = max(pos + size - 2000, pos)
            segment = content[search_start:end]

            # Prefer blank line, then single newline
            blank_line = segment.rfind("\n\n")
            if blank_line >= 0:
                end = search_start + blank_line + 2
            else:
                newline = segment.rfind("\n")
                if newline >= 0:
                    end = search_start + newline + 1

        chunk_content = content[pos:end]
        chunks.append({
            "index": index,
            "start_char": pos,
            "end_char": end,
            "char_count": len(chunk_content),
            "content": chunk_content,
        })

        # Advance position, accounting for overlap
        pos = max(end - overlap, pos + 1)
        index += 1

    json.dump(chunks, sys.stdout, indent=2)
    print()


def cmd_boundaries(path):
    """Detect natural boundaries in a file."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    boundaries = []
    for i, line in enumerate(lines, 1):
        # Markdown headers
        if re.match(r"^#{1,6}\s", line):
            boundaries.append({"line": i, "type": "markdown_header", "text": line.rstrip()})
        # Python defs and classes
        elif re.match(r"^(def |class )", line):
            boundaries.append({"line": i, "type": "python_def", "text": line.rstrip()})
        # Blank line sequences (paragraph breaks)
        elif (line.strip() == "" and i > 1 and i < len(lines)
              and lines[i - 2].strip() != "" and i < len(lines) and lines[i].strip() != ""):
            boundaries.append({"line": i, "type": "paragraph_break", "text": ""})

    json.dump(boundaries, sys.stdout, indent=2)
    print()


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    path = sys.argv[2]

    if not os.path.isfile(path):
        print(f"Error: {path} is not a file", file=sys.stderr)
        sys.exit(1)

    if cmd == "info":
        cmd_info(path)
    elif cmd == "chunk":
        size = 100_000
        overlap = 500
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--size" and i + 1 < len(args):
                size = int(args[i + 1])
                i += 2
            elif args[i] == "--overlap" and i + 1 < len(args):
                overlap = int(args[i + 1])
                i += 2
            else:
                print(f"Unknown argument: {args[i]}", file=sys.stderr)
                sys.exit(1)
        cmd_chunk(path, size, overlap)
    elif cmd == "boundaries":
        cmd_boundaries(path)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
