"""Removes a model's hidden reasoning from a reply, keeping only the answer.

Used when a reply is generated and again when old replies are loaded from
history, so replies stored before this cleanup existed display correctly too.
"""
import re

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
# Reasoning that hit the length limit never gets its closing tag.
UNCLOSED_THINK = re.compile(r"<think>.*", re.IGNORECASE | re.DOTALL)
THINKING_PREAMBLE = re.compile(r"^\s*thinking\s+process\s*:.*?(?=(?:final\s+answer\s*:)|$)", re.IGNORECASE | re.DOTALL)
FINAL_ANSWER = re.compile(r"^\s*final\s+answer\s*:\s*", re.IGNORECASE)

NO_ANSWER_NOTE = "(This reply was cut off before the model finished its answer.)"
# Appended when a reply stops at the length limit, so it is never cut off silently.
LENGTH_NOTE = "\n\n*(Reply shortened: it reached the length limit.)*"


def clean_reply(text):
    text = THINK_BLOCK.sub("", text or "")
    if re.search(r"</think>", text, re.IGNORECASE):
        # Reasoning without an opening tag: keep what follows the closing tag.
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]
    text = UNCLOSED_THINK.sub("", text)
    text = THINKING_PREAMBLE.sub("", text.strip())
    text = FINAL_ANSWER.sub("", text)
    return text.strip()
