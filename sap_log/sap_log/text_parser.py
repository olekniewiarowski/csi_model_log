"""Simple parser for CSI ET/ETABS text files that use `$` headers.

Rules implemented:
- A header line starts with `$` at the beginning of the line.
- The key is the header text with whitespace collapsed to single underscores.
- The value is a single string containing all lines (including internal newlines)
  from the header until the next header (excluding the header line itself).

Functions:
- parse_et_text(text: str) -> dict
- parse_et_file(path: str, encoding: str = 'utf-8') -> dict

Example usage:
>>> from sap_log.sap_log.text_parser import parse_et_file
>>> d = parse_et_file('reference_files/Model1.$et')
>>> print(list(d.keys())[:5])
"""

from __future__ import annotations

import re
from typing import Dict


def _normalize_header(header: str) -> str:
	"""Normalize header text: collapse whitespace to single underscore.

	Keeps other characters (like `-`) intact.
	"""
	h = header.strip()
	# collapse any whitespace run to single underscore
	return re.sub(r"\s+", "_", h)


def parse_et_text(text: str) -> Dict[str, str]:
	"""Parse a complete ET text (string) into a dict of header->content string.

	Header lines are those where the (left-stripped) line starts with `$`.

	Returns:
		Dict where keys are normalized headers and values are the block text
		(preserving original internal line breaks) between that header and
		the next header. Leading/trailing blank lines inside a block are
		trimmed.
	"""
	lines = text.splitlines(keepends=True)

	result: Dict[str, str] = {}
	current_key = None
	buffer = []

	for raw_line in lines:
		# preserve line as-is in buffer, but strip only for header detection
		lstrip = raw_line.lstrip()
		if lstrip.startswith("$"):
			# commit previous buffer
			if current_key is not None:
				# join and strip leading/trailing newlines/spaces
				block = ''.join(buffer).strip('\n')
				result[current_key] = block
			# start new header
			header_text = lstrip[1:].strip()
			current_key = _normalize_header(header_text)
			buffer = []
			continue
		# not a header: if we've seen a header, collect lines
		if current_key is not None:
			buffer.append(raw_line)
		else:
			# lines before first header are ignored (or could be stored under
			# a special key). We'll ignore to follow the spec.
			continue

	# commit final buffer
	if current_key is not None:
		block = ''.join(buffer).strip('\n')
		result[current_key] = block

	return result


def parse_et_file(path: str, encoding: str = 'utf-8') -> Dict[str, str]:
	"""Read a file and parse it with `parse_et_text`.

	Args:
		path: filesystem path to the ET text file.
		encoding: file encoding (default utf-8).
	Returns:
		dict mapping normalized header -> block text.
	"""
	with open(path, 'r', encoding=encoding, errors='replace') as f:
		text = f.read()
	return parse_et_text(text)


if __name__ == '__main__':
	import json
	import os
	# Run quick parse of reference file (if present), print summary and write JSON.
	repo_root = os.path.dirname(os.path.dirname(__file__))
	default_path = os.path.join(repo_root, 'reference_files', 'Model1.$et')
	if os.path.exists(default_path):
		parsed = parse_et_file(default_path)
		print(f'Parsed {len(parsed)} headers from: {default_path}')
		# print first 5 keys
		for i, k in enumerate(parsed.keys()):
			print('-', k)
			if i >= 4:
				break
		out_path = default_path + '.json'
		try:
			with open(out_path, 'w', encoding='utf-8') as out_f:
				json.dump(parsed, out_f, indent=2, ensure_ascii=False)
			print('Wrote parsed JSON to', out_path)
		except Exception as exc:
			print('Failed to write JSON file:', exc)
	else:
		print('No default file found at', default_path)

