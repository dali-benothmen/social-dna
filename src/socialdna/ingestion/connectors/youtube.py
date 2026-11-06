"""One fixed, authenticated metadata endpoint; no player, media or caption downloads."""

import ipaddress
import json
import socket
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from socialdna.core.time import format_utc, utc_now
from socialdna.domain.acquisition import (
    POLICY_VERSION,
    YOUTUBE_FIELDS,
    CaptureFailure,
    CaptureManifest,
)

ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
FIELDS = (
    "items(id,snippet(channelId,channelTitle,title,description,publishedAt,categoryId,"
    "defaultLanguage,defaultAudioLanguage),contentDetails(duration),"
    "statistics(viewCount,likeCount,commentCount))"
)


def _public_api_address() -> None:
    try:
        addresses = socket.getaddrinfo("www.googleapis.com", 443, type=socket.SOCK_STREAM)
        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_global for item in addresses
        ):
            raise CaptureFailure(
                "unsafe_api_address", "The API host resolved to a non-public address."
            )
    except OSError:
        raise CaptureFailure(
            "network_unavailable", "Cannot resolve the official API endpoint.", retry_after=60
        ) from None


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate response key")
        result[key] = value
    return result


def fetch(
    external_id: str,
    api_key: str,
    *,
    retention_days: int = 7,
    max_bytes: int = 1_048_576,
    timeout: float = 20,
    client: httpx.Client | None = None,
) -> CaptureManifest:
    """Accept an injected transport for tests, not an overridable production endpoint."""
    owned = client is None
    if owned:
        _public_api_address()
        client = httpx.Client(
            timeout=httpx.Timeout(timeout), follow_redirects=False, trust_env=False
        )
    assert client is not None
    started = time.monotonic()
    try:
        with client.stream(
            "GET",
            ENDPOINT,
            params={
                "part": "snippet,contentDetails,statistics",
                "id": external_id,
                "fields": FIELDS,
            },
            headers={
                "X-Goog-Api-Key": api_key,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            follow_redirects=False,
        ) as response:
            if response.status_code in (401, 403):
                # Do not echo Google's error body, request URL or credential-bearing exception.
                raise CaptureFailure(
                    "youtube_access_denied",
                    "The API rejected access; check the key, enabled API and quota.",
                    permission=True,
                )
            if response.status_code == 429 or response.status_code >= 500:
                retry = response.headers.get("Retry-After", "60")
                delay = min(max(int(retry), 1), 3600) if retry.isdecimal() else 60
                raise CaptureFailure(
                    "youtube_retry_later",
                    "The API is rate limited or unavailable.",
                    retry_after=delay,
                )
            if response.status_code != 200:
                raise CaptureFailure(
                    "youtube_response_unavailable",
                    "The official API did not return a successful metadata response.",
                )
            if (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
                != "application/json"
            ):
                raise CaptureFailure("invalid_response", "The API did not return JSON metadata.")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise CaptureFailure(
                    "invalid_response", "Encoded metadata responses are not accepted."
                )
            length = response.headers.get("content-length", "")
            if length.isdecimal() and int(length) > max_bytes:
                raise CaptureFailure(
                    "response_budget_exceeded", "The metadata response exceeds its byte budget."
                )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes(chunk_size=65_536):
                size += len(chunk)
                if size > max_bytes or time.monotonic() - started > timeout:
                    raise CaptureFailure(
                        "response_budget_exceeded",
                        "The metadata response exceeded its byte/time budget.",
                    )
                chunks.append(chunk)
        payload = json.loads(
            b"".join(chunks),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        if items == []:
            raise CaptureFailure(
                "post_not_returned",
                "The API did not return this post; it may be private, deleted or unavailable.",
            )
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise ValueError("Expected one post")
        item = items[0]
        values: dict[str, str | None] = {}
        for field in YOUTUBE_FIELDS:
            raw: Any = item
            for part in field.split("/"):
                raw = raw.get(part) if isinstance(raw, dict) else None
            if raw is not None and (not isinstance(raw, str) or len(raw) > 10_000):
                raise ValueError("Unexpected native field type/size")
            if field.startswith("statistics/") and raw is not None and not raw.isdecimal():
                raise ValueError("Expected a source-native unsigned count string")
            values[field] = raw
        captured = utc_now()
        expires = format_utc(datetime.fromisoformat(captured) + timedelta(days=retention_days))
        return CaptureManifest(
            policy_version=POLICY_VERSION,
            source_url=f"https://www.youtube.com/watch?v={external_id}",
            external_id=external_id,
            captured_at=captured,
            expires_at=expires,
            fields=values,
            response_bytes=size,
        )
    except CaptureFailure:
        raise
    except httpx.HTTPError:
        raise CaptureFailure(
            "network_unavailable", "The metadata request failed or timed out.", retry_after=60
        ) from None
    except (ValueError, UnicodeError, KeyError, TypeError):
        raise CaptureFailure(
            "invalid_response", "The API returned invalid or mismatched metadata."
        ) from None
    finally:
        if owned:
            client.close()
