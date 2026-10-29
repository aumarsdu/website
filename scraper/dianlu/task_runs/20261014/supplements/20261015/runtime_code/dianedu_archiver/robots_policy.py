"""RFC 9309 matching: merged agent groups, wildcard/$, longest rule.

Source: https://www.rfc-editor.org/rfc/rfc9309.html#section-2.2
Unknown malformed rule paths fail closed for the selected group.
"""
import re
from urllib.parse import quote, urlparse


def octets(value: str) -> str:
    def encoded(match):
        character = chr(int(match.group()[1:], 16))
        return character if character.isascii() and (character.isalnum() or character in "-._~") else match.group().upper()
    return quote(re.sub(r"%[0-9a-fA-F]{2}", encoded, value), safe="/%?&=+:;,@!$()*-._~")


class RobotsPolicy:
    def __init__(self, text: str, agent: str):
        groups = []
        group = {"agents": [], "rules": [], "delay": 0.0}
        have_rules = False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if have_rules:
                    groups.append(group)
                    group = {"agents": [], "rules": [], "delay": 0.0}
                    have_rules = False
                group["agents"].append(value.lower())
            elif group["agents"] and key in {"allow", "disallow"}:
                have_rules = True
                if value:
                    group["rules"].append((key == "allow", value))
            elif group["agents"] and key in {"crawl-delay", "request-rate"}:
                have_rules = True
                try:
                    if key == "request-rate":
                        requests, seconds = (float(x) for x in value.split("/", 1))
                        delay = seconds / requests
                    else:
                        delay = float(value)
                    group["delay"] = max(group["delay"], delay)
                except (ValueError, ZeroDivisionError):
                    group["delay"] = float("inf")
        groups.append(group)
        token = agent.split("/", 1)[0].lower()
        selected = [x for x in groups if token in x["agents"]]
        if not selected:
            selected = [x for x in groups if "*" in x["agents"]]
        self.rules = [rule for group in selected for rule in group["rules"]]
        self.delay = max((x["delay"] for x in selected), default=0)

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        path = octets((parsed.path or "/") + (";" + parsed.params if parsed.params else "") + ("?" + parsed.query if parsed.query else ""))
        matches = []
        for allow, pattern in self.rules:
            if not pattern.startswith("/"):
                return False
            pattern = octets(pattern)
            ending = pattern.endswith("$")
            body = pattern[:-1] if ending else pattern
            expression = "^" + re.escape(body).replace(r"\*", ".*") + ("$" if ending else "")
            if re.search(expression, path):
                matches.append((len(body.replace("*", "").encode()), allow))
        return max(matches)[1] if matches else True
