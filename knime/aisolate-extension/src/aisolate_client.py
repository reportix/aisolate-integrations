"""AIsolate's HTTP calls for the KNIME nodes: discovery, sign-in, the airlocks, the chat. Standard library only."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

ASK_TIMEOUT = 600  # above the airlock's eight-minute exchange budget
TIMEOUT = 30
SCOPE = "openid profile email"


class AIsolateError(Exception):
    pass


def _call(method: str, url: str, headers: dict | None = None, body: bytes | None = None, timeout: int = TIMEOUT):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as e:
        raise AIsolateError(f"{method} {url} answered {e.code}: {_reason(e.read())}") from None
    except urllib.error.URLError as e:
        raise AIsolateError(f"{method} {url} failed: {e.reason}") from None


def _reason(body: bytes) -> str:
    # Keycloak says error_description, AIsolate's problem documents say detail or title
    try:
        doc = json.loads(body)
    except ValueError:
        return body.decode(errors="replace")[:200] or "no body"
    return doc.get("error_description") or doc.get("detail") or doc.get("title") or doc.get("error") or str(doc)[:200]


def token_endpoint(aisolate_url: str) -> str:
    """The identity provider's token endpoint, found from AIsolate's RFC 9728 metadata."""
    resource = _call("GET", urllib.parse.urljoin(aisolate_url, "/.well-known/oauth-protected-resource"))
    issuer = resource["authorization_servers"][0].rstrip("/")
    return _call("GET", issuer + "/.well-known/openid-configuration")["token_endpoint"]


def sign_in(token_url: str, client_id: str, client_secret: str) -> str:
    """An access token for the client itself: the client-credentials grant, no user."""
    pair = f"{urllib.parse.quote(client_id, safe='')}:{urllib.parse.quote(client_secret, safe='')}"
    headers = {"Authorization": "Basic " + base64.b64encode(pair.encode()).decode(),
               "Content-Type": "application/x-www-form-urlencoded"}
    form = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode()
    return _call("POST", token_url, headers, form)["access_token"]


def airlocks(aisolate_url: str, token: str) -> list:
    """The airlocks that admit this token's user and client, each with its chat endpoint."""
    return _call("GET", urllib.parse.urljoin(aisolate_url, "/v1/airlocks"), {"Authorization": "Bearer " + token})


def ask(aisolate_url: str, endpoint: str, token: str, question: str) -> dict:
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
               # that value alone: anything listing */* or text/event-stream gets the stream
               "Accept": "application/json"}
    body = json.dumps({"message": question}).encode()
    return _call("POST", urllib.parse.urljoin(aisolate_url, endpoint), headers, body, ASK_TIMEOUT)


def choices(found: list) -> list:
    """One (endpoint, label, description) per airlock, for a dropdown."""
    return [(a["endpoint"], a["name"], f"Space {a['space']}" + (f": {a['description']}" if a.get("description") else ""))
            for a in found]


def answer_row(answer: dict) -> dict:
    """The answer's columns: the text, its provenance and evidence."""
    provenance = answer.get("provenance") or {}
    return {
        "answer": answer.get("answer", ""),
        "provenance": provenance.get("status", ""),
        "sourced": int(provenance.get("sourced", 0)),
        "computed": int(provenance.get("computed", 0)),
        "unsourced": int(provenance.get("unsourced", 0)),
        "mismatch": int(provenance.get("mismatch", 0)),
        "evidence": json.dumps(answer.get("evidence", [])),
        "revision": answer.get("revision", ""),
        "trace_id": answer.get("trace_id", ""),
    }
