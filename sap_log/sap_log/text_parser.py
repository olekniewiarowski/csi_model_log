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


def _tokenize_line(line: str) -> list:
	"""Tokenize a line preserving quoted strings as single tokens.

	Returns a list of tokens with surrounding double-quotes removed.
	"""
	parts = re.findall(r'"[^"]*"|\S+', line)
	tokens = [p[1:-1] if p.startswith('"') and p.endswith('"') else p for p in parts]
	return tokens


def _convert_token(tok: str):
	"""Try to convert token to int or float, otherwise return original string."""
	try:
		return int(tok)
	except Exception:
		try:
			return float(tok)
		except Exception:
			return tok


def process_special_sections(parsed: Dict[str, str]) -> Dict[str, dict]:
	"""Post-process certain sections into structured nested dictionaries.

	For each of the following normalized headers:
	  - `POINT_COORDINATES`
	  - `LINE_CONNECTIVITIES`
	  - `LINE_ASSIGNS`

	We parse each non-empty line, tokenize it (preserving quoted strings),
	and produce a mapping where the key is the second token (usually an
	identifier like `1`, `C1`, etc.) and the value is a dict with:
	  - `command`: first token (e.g., `POINT`, `LINE`, `LINEASSIGN`)
	  - `args`: list of converted tokens after the second token
	  - `raw_tokens`: the full token list (with quotes removed)

	Returns a dict mapping section_name -> structured mapping.
	"""
	out = {}
	sections = [
		'POINT_COORDINATES',
		'LINE_CONNECTIVITIES',
		'LINE_ASSIGNS',
	]

	for sec in sections:
		if sec not in parsed:
			continue
		block = parsed[sec]
		lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
		mapping = {}
		for ln in lines:
			tokens = _tokenize_line(ln)
			if not tokens:
				continue
			# Use second token as key when present, otherwise use an index
			if len(tokens) >= 2:
				key = tokens[1]
			else:
				# fallback - use the command plus a running index
				key = f"{tokens[0]}_{len(mapping)+1}"

			# args are tokens after the second token
			args_raw = tokens[2:]
			args = [_convert_token(t) for t in args_raw]

			mapping[key] = {
				'command': tokens[0],
				'args': args,
				'raw_tokens': tokens,
			}

		out[sec] = mapping

	return out


def parse_and_structure_file(path: str, encoding: str = 'utf-8') -> Dict[str, object]:
	"""Parse file and return parsed sections with special sections structured.

	The returned dict contains the original parsed text blocks, and an
	additional key `_structured` with processed mappings for the special
	sections.
	"""
	parsed = parse_et_file(path, encoding=encoding)
	structured = process_special_sections(parsed)
	result = dict(parsed)
	result['_structured'] = structured
	return result


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

		# also write a structured JSON file with nested dicts for special sections
		structured = parse_and_structure_file(default_path)
		out_struct = default_path + '.structured.json'
		try:
			with open(out_struct, 'w', encoding='utf-8') as out_f2:
				json.dump(structured, out_f2, indent=2, ensure_ascii=False)
			print('Wrote structured JSON to', out_struct)
		except Exception as exc:
			print('Failed to write structured JSON file:', exc)
	else:
		print('No default file found at', default_path)

