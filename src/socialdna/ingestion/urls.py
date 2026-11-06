"""Offline URL identities. User links are never network request destinations."""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from socialdna.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class URLTarget:
    platform: Literal["youtube", "instagram", "tiktok"]
    kind: Literal["post", "account"]
    external_id: str
    canonical_url: str


def parse_url(value: str) -> URLTarget:
    """Recognize exact supported shapes, discard tracking, and reject ambiguous identities."""
    try:
        url = urlsplit(value.strip())
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or "\\" in value
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError()
        host = url.hostname or ""
        parts = url.path.strip("/").split("/")
        query = parse_qs(url.query, keep_blank_values=True, strict_parsing=False)
        if {key.casefold() for key in query} & {
            "key",
            "api_key",
            "access_token",
            "token",
            "password",
            "auth",
        }:
            raise ValueError()
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            identity = ""
            if host == "youtu.be" and len(parts) == 1:
                identity = parts[0]
            elif parts == ["watch"] and len(query.get("v", [])) == 1:
                identity = query["v"][0]
            elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
                identity = parts[1]
            elif (len(parts) == 1 and re.fullmatch(r"@[A-Za-z0-9_.-]{1,100}", parts[0])) or (
                len(parts) == 2
                and parts[0] == "channel"
                and re.fullmatch(r"UC[A-Za-z0-9_-]{22}", parts[1])
            ):
                alias = "/".join(parts)
                return URLTarget("youtube", "account", alias, f"https://www.youtube.com/{alias}")
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", identity):
                return URLTarget(
                    "youtube", "post", identity, f"https://www.youtube.com/watch?v={identity}"
                )
        elif host in {"instagram.com", "www.instagram.com"}:
            if (
                len(parts) == 2
                and parts[0] in {"p", "reel", "tv"}
                and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", parts[1])
            ):
                return URLTarget(
                    "instagram",
                    "post",
                    parts[1],
                    f"https://www.instagram.com/{parts[0]}/{parts[1]}/",
                )
            if (
                len(parts) == 1
                and re.fullmatch(r"[A-Za-z0-9_.]{1,30}", parts[0])
                and parts[0] not in {"accounts", "explore", "direct", "stories", "reel", "p", "tv"}
            ):
                return URLTarget(
                    "instagram", "account", parts[0], f"https://www.instagram.com/{parts[0]}/"
                )
        elif host in {"tiktok.com", "www.tiktok.com"}:
            if parts and re.fullmatch(r"@[A-Za-z0-9_.]{1,100}", parts[0]):
                if len(parts) == 1:
                    return URLTarget(
                        "tiktok", "account", parts[0], f"https://www.tiktok.com/{parts[0]}"
                    )
                if (
                    len(parts) == 3
                    and parts[1] in {"video", "photo"}
                    and re.fullmatch(r"[0-9]{1,30}", parts[2])
                ):
                    return URLTarget(
                        "tiktok", "post", parts[2], "https://www.tiktok.com/" + "/".join(parts)
                    )
    except ValueError:
        pass
    raise ConfigurationError(
        "Use a supported HTTPS YouTube, Instagram or TikTok post/profile URL without "
        "credentials, custom ports or secret-bearing parameters. "
        "Short-link redirects are not fetched."
    )
