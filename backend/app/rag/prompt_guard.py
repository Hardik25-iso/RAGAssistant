"""First-line prompt-injection filter.

This is defence in depth, not the main control: even if an attack slips past,
retrieval is already restricted to the student's own chunks, so there is no
other user's data in the context to leak.
"""
import re
import unicodedata
from dataclasses import dataclass

PATTERNS: list[tuple[str, str]] = [
    (r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|your|the|system)\b.{0,20}\b(instructions?|rules?|prompts?|directions?|context)\b", "instruction override"),
    (r"\b(reveal|show|print|repeat|display|leak|output|tell me)\b.{0,40}\b(system|hidden|initial|developer)\s*(prompt|message|instructions?)\b", "system prompt extraction"),
    (r"\byour\s+(system\s+)?(prompt|instructions)\b.{0,20}\b(verbatim|word for word|exactly)\b", "system prompt extraction"),
    (r"\b(other|another|all|every|different)\s+(users?|students?|accounts?|people)('s|s')?\b.{0,40}\b(files?|documents?|notes|data|uploads?|chats?|pdfs?|slides?)\b", "cross-user data request"),
    (r"\b(files?|documents?|notes|data|uploads?)\b.{0,20}\b(of|from|belonging to)\s+(other|another|all)\s+(users?|students?)\b", "cross-user data request"),
    (r"\b(you are now|act as|pretend to be|roleplay as|from now on you)\b.{0,40}\b(dan|jailbreak|unrestricted|unfiltered|developer mode|admin|root)\b", "role hijack"),
    (r"\b(developer|god|jailbreak|dan)\s+mode\b", "role hijack"),
    (r"<\s*/?\s*(system|assistant|im_start|im_end)\s*>|\[/?(inst|system)\]", "chat-template injection"),
    (r"\b(your|the app'?s?|server'?s?|backend'?s?)\s+(api[_\s-]?key|jwt[_\s-]?secret|database[_\s-]?url|aws[_\s-]?(secret|access)[_\s-]?key|credentials|env(ironment)? variables)\b", "secret extraction"),
]
# Note: no SQL keyword filter. DBMS students legitimately ask about SELECT/JOIN,
# and SQL injection is already impossible because all queries are parameterised (SQLAlchemy ORM).
_COMPILED = [(re.compile(p, re.IGNORECASE | re.DOTALL), reason) for p, reason in PATTERNS]
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


@dataclass
class GuardResult:
    blocked: bool
    reason: str | None = None


def normalize(text: str) -> str:
    # NFKC folds look-alike characters; zero-width chars are a common evasion trick
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    return " ".join(text.split())


def check_prompt(question: str) -> GuardResult:
    text = normalize(question)
    for pattern, reason in _COMPILED:
        if pattern.search(text):
            return GuardResult(True, reason)
    return GuardResult(False)


BLOCKED_REPLY = (
    "I can only help with questions about your own study material. "
    "This request looks like an attempt to change my instructions or access data "
    "that isn't yours, so I've blocked it. Try rephrasing your question about the topic."
)
