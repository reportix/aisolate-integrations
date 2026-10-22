import base64
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import aisolate_client as aisolate  # noqa: E402

ANSWER = {"answer": "Your gross salary is 5,200.00 EUR.", "dont_know": False,
          "provenance": {"status": "all_sourced", "sourced": 1, "computed": 0, "unsourced": 0, "mismatch": 0},
          "evidence": [{"id": "ev-1", "source": "read_my_records", "name": "hr.compensation", "rows": 1, "data_source": "hr"}],
          "revision": "a2cf258ece3d", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}
ENDPOINT = "/v1/spaces/hr-space/airlocks/hr-contracts/chat"
AIRLOCKS = [{"id": "hr-contracts", "space": "hr-space", "name": "HR Contracts", "description": "Contracts",
             "endpoint": ENDPOINT, "tools": []}]


@pytest.fixture
def server():
    """Keycloak and AIsolate on one port; records each request as (method, path, headers, body)."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            seen.append((method, self.path, dict(self.headers), body))
            base = f"http://127.0.0.1:{self.server.server_port}"
            routes = {
                ("GET", "/.well-known/oauth-protected-resource"): (200, {"authorization_servers": [base + "/realms/acme"]}),
                ("GET", "/realms/acme/.well-known/openid-configuration"): (200, {"token_endpoint": base + "/realms/acme/token"}),
                ("GET", "/v1/airlocks"): (200, AIRLOCKS),
                ("POST", ENDPOINT): (200, ANSWER),
            }
            if (method, self.path) == ("POST", "/realms/acme/token"):
                ok = self.headers.get("Authorization") == "Basic " + base64.b64encode(b"knime:s3cret").decode()
                return self._reply(200 if ok else 401, {"access_token": "tok"} if ok else
                                   {"error": "unauthorized_client", "error_description": "Invalid client or Invalid client credentials"})
            self._reply(*routes.get((method, self.path), (404, {"title": "Not Found"})))

        def _reply(self, code, doc):
            data = json.dumps(doc).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", seen
    httpd.shutdown()


def test_given_protected_resource_metadata_when_token_endpoint_then_the_issuers_token_url(server):
    # Arrange
    url, _ = server

    # Act
    token_url = aisolate.token_endpoint(url)

    # Assert
    assert token_url == url + "/realms/acme/token"


def test_given_client_when_sign_in_then_client_credentials_grant_with_basic_auth(server):
    # Arrange
    url, seen = server

    # Act
    token = aisolate.sign_in(url + "/realms/acme/token", "knime", "s3cret")

    # Assert
    assert token == "tok"
    form = urllib.parse.parse_qs(seen[-1][3])
    assert form == {"grant_type": ["client_credentials"], "scope": ["openid profile email"]}


def test_given_wrong_secret_when_sign_in_then_error_carries_the_identity_providers_reason(server):
    # Arrange
    url, _ = server

    # Act
    with pytest.raises(aisolate.AIsolateError) as error:
        aisolate.sign_in(url + "/realms/acme/token", "knime", "wrong")

    # Assert
    assert "401: Invalid client or Invalid client credentials" in str(error.value)


def test_given_admitted_token_when_airlocks_then_one_choice_per_airlock(server):
    # Arrange
    url, seen = server

    # Act
    choices = aisolate.choices(aisolate.airlocks(url, "tok"))

    # Assert
    assert choices == [(ENDPOINT, "HR Contracts", "Space hr-space: Contracts")]
    assert seen[-1][2]["Authorization"] == "Bearer tok"


def test_given_question_when_ask_then_json_accept_bearer_and_message_body(server):
    # Arrange
    url, seen = server

    # Act
    answer = aisolate.ask(url, ENDPOINT, "tok", "What is my gross salary?")

    # Assert
    _, _, headers, body = seen[-1]
    assert (headers["Accept"], headers["Authorization"]) == ("application/json", "Bearer tok")
    assert json.loads(body) == {"message": "What is my gross salary?"}
    assert aisolate.answer_row(answer) == {
        "answer": "Your gross salary is 5,200.00 EUR.", "provenance": "all_sourced",
        "sourced": 1, "computed": 0, "unsourced": 0, "mismatch": 0, "evidence": json.dumps(ANSWER["evidence"]),
        "revision": "a2cf258ece3d", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}


def test_given_denied_question_when_answer_row_then_no_figures_and_empty_evidence():
    # Arrange
    answer = {"answer": "", "dont_know": True, "provenance": {"status": "no_figures"}, "evidence": []}

    # Act
    row = aisolate.answer_row(answer)

    # Assert
    assert (row["provenance"], row["evidence"], row["sourced"]) == ("no_figures", "[]", 0)
    assert "dont_know" not in row
