#!/usr/bin/env python3
"""
Postfix pipe script: reads an incoming email from stdin,
extracts the 6-digit verification code, and writes it to
/tmp/mailcodes/<to_addr> so the bot can pick it up.
"""
import sys
import re
import email
import os
import json
import time

CODES_DIR = "/tmp/mailcodes"
os.makedirs(CODES_DIR, exist_ok=True)

raw = sys.stdin.buffer.read()
msg = email.message_from_bytes(raw)

def _extract_addr(header_val):
    if not header_val:
        return ""
    header_val = header_val.strip()
    m = re.search(r'<([^>]+)>', header_val)
    if m:
        return m.group(1).strip().lower()
    return header_val.strip("<>").strip().lower()

# Try headers in order of reliability
to_addr = (
    _extract_addr(msg.get("X-Original-To")) or
    _extract_addr(msg.get("Delivered-To")) or
    _extract_addr(msg.get("To")) or
    ""
)

body = ""
if msg.is_multipart():
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
                break
else:
    payload = msg.get_payload(decode=True)
    if payload:
        body = payload.decode("utf-8", errors="ignore")

code_match = re.search(r'\b(\d{6})\b', body)
if code_match and to_addr and "@" in to_addr:
    code = code_match.group(1)
    fname = to_addr.replace("@", "_at_").replace("/", "_")
    code_file = os.path.join(CODES_DIR, fname)
    with open(code_file, "w") as f:
        json.dump({"code": code, "ts": time.time(), "to": to_addr}, f)
