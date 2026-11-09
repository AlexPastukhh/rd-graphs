"""Repo typed client transport safety: bounded results, no redirects or leaks."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from fortis_approvals.core import Denied
from fortis_approvals import repo_sonar_tools as bridge


class _Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class _Opener:
    def __init__(self, body, status=200):
        self.response = _Response(body, status=status)
        self.request = None

    def open(self, request, timeout):
        self.request = request
        if callable(self.response.body):
            return _Response(self.response.body(request),
                             status=self.response.status)
        return self.response


class RepoSonarToolsTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="repo-sonar-client-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.grant = root / "grant"
        self.grant.write_text("R7-TEST-CLIENT-GRANT-01234567890\n")
        self.grant.chmod(0o600)
        self.cert = root / "server.crt"
        self.cert.write_text("test-only public certificate placeholder")
        self.cert.chmod(0o644)

    def invoke(self, opener, *, tool="sonar.get_quality_gate",
               target="trusted_project_000", **kwargs):
        with patch.object(bridge.ssl, "create_default_context",
                          return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
            return bridge.call(
                tool, target=target, grant_path=self.grant,
                certificate_path=self.cert, transport=opener, **kwargs)

    def test_non_string_status_is_rejected_without_type_error(self):
        request_id = "00000000-0000-4000-8000-000000000001"
        opener = _Opener(json.dumps({
            "requestId": request_id, "state": []
        }).encode())
        with self.assertRaisesRegex(Denied, "FORTIS_STATUS_RESPONSE_INVALID"):
            self.invoke(opener, tool="approvals.request_status",
                        request_id=request_id)

    def test_non_finite_json_response_is_rejected(self):
        def invalid_response(request):
            request_id = json.loads(request.data)['requestId']
            return (
                '{"requestId":%s,"service":"sonarcloud",'
                '"operation":"get_quality_gate","data":{"status":NaN}}'
                % json.dumps(request_id)).encode()

        opener = _Opener(invalid_response)
        with self.assertRaisesRegex(
                Denied, "FORTIS_UPSTREAM_UNAVAILABLE_OR_INVALID"):
            self.invoke(opener)

    def test_response_limit_is_checked_before_json_decode(self):
        opener = _Opener(b"x" * (bridge.MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(Denied, "FORTIS_RESPONSE_TOO_LARGE"):
            self.invoke(opener)

    def test_nonfinite_exponent_is_rejected(self):
        opener = _Opener(
            b'{"requestId":"00000000-0000-4000-8000-000000000001",'
            b'"service":"sonarcloud","operation":"get_quality_gate",'
            b'"data":{"overflow":1e9999}}')
        with self.assertRaisesRegex(
                Denied, "FORTIS_UPSTREAM_UNAVAILABLE_OR_INVALID"):
            self.invoke(opener)

    def test_duplicate_json_fields_are_rejected(self):
        def duplicate_response(request):
            request_id = json.loads(request.data)['requestId']
            return (
                '{"requestId":%s,"service":"sonarcloud",'
                '"operation":"get_quality_gate",'
                '"data":{"status":"OK","status":"ERROR"}}'
                % json.dumps(request_id)).encode()

        with self.assertRaisesRegex(
                Denied, "FORTIS_UPSTREAM_UNAVAILABLE_OR_INVALID"):
            self.invoke(_Opener(duplicate_response))

    def test_deeply_nested_json_is_rejected_without_recursion_error(self):
        opener = _Opener(b"[" * 1200 + b"]" * 1200)
        with self.assertRaisesRegex(
                Denied, "FORTIS_UPSTREAM_UNAVAILABLE_OR_INVALID"):
            self.invoke(opener)

    def test_read_rejects_http_202(self):
        with self.assertRaisesRegex(Denied, "FORTIS_HTTP_UNEXPECTED_STATUS"):
            self.invoke(_Opener(b"{}", status=202))

    def test_http_error_body_and_headers_are_not_exposed(self):
        grant_value = self.grant.read_text().strip()

        class ErrorHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(401)
                self.send_header("X-Diagnostic", "Bearer " + grant_value)
                self.end_headers()
                self.wfile.write(("PRIVATE UPSTREAM " + grant_value).encode())

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), ErrorHandler)
        thread = Thread(target=server.handle_request, daemon=True)
        thread.start()
        try:
            with (patch.object(
                    bridge, "ENDPOINT",
                    "http://127.0.0.1:%d" % server.server_port),
                  patch.object(
                    bridge.ssl, "create_default_context",
                    return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))):
                with self.assertRaisesRegex(Denied, "FORTIS_HTTP_401") as caught:
                    bridge.call(
                        "sonar.get_quality_gate",
                        target="trusted_project_000",
                        grant_path=self.grant,
                        certificate_path=self.cert)
        finally:
            server.server_close()
            thread.join(timeout=2)
        self.assertNotIn(grant_value, str(caught.exception))
        self.assertNotIn("PRIVATE UPSTREAM", str(caught.exception))

    def test_http_redirect_is_rejected_without_following_or_forwarding_grant(self):
        forwarded = []

        class SinkHandler(BaseHTTPRequestHandler):
            def _capture(self):
                forwarded.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')

            def do_GET(self):
                self._capture()

            def do_POST(self):
                self._capture()

            def log_message(self, *_args):
                pass

        sink = ThreadingHTTPServer(("127.0.0.1", 0), SinkHandler)

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307)
                self.send_header(
                    "Location",
                    "http://127.0.0.1:%d/capture" % sink.server_port)
                self.end_headers()

            def log_message(self, *_args):
                pass

        source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        threads = [
            Thread(target=sink.serve_forever, daemon=True),
            Thread(target=source.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            with (patch.object(
                    bridge, "ENDPOINT",
                    "http://127.0.0.1:%d" % source.server_port),
                  patch.object(
                    bridge.ssl, "create_default_context",
                    return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))):
                with self.assertRaisesRegex(Denied, "FORTIS_REDIRECT_DENIED"):
                    bridge.call(
                        "sonar.get_quality_gate",
                        target="trusted_project_000",
                        grant_path=self.grant,
                        certificate_path=self.cert)
        finally:
            source.shutdown()
            sink.shutdown()
            source.server_close()
            sink.server_close()
            for thread in threads:
                thread.join(timeout=2)
        self.assertEqual(forwarded, [])


    def test_all_four_read_tools_send_only_typed_read_envelopes(self):
        cases = (
            ("sonar.list_projects", "list_projects", "trusted_org", None),
            ("sonar.list_issues", "list_issues", "trusted_project_000", None),
            ("sonar.get_issue", "get_issue", "trusted_project_000-I001",
             "trusted_project_000"),
            ("sonar.get_quality_gate", "get_quality_gate",
             "trusted_project_000", None),
        )
        for tool, operation, target, project_key in cases:
            def response(request, operation=operation):
                sent = json.loads(request.data)
                return json.dumps({
                    "requestId": sent["requestId"],
                    "service": "sonarcloud",
                    "operation": operation,
                    "data": {"operation": operation},
                }).encode()
            opener = _Opener(response)
            result = self.invoke(
                opener, tool=tool, target=target, project_key=project_key)
            sent = json.loads(opener.request.data)
            with self.subTest(tool=tool):
                self.assertEqual(result["operation"], operation)
                self.assertEqual(opener.request.get_method(), "POST")
                self.assertTrue(opener.request.full_url.endswith("/v1/reads"))
                self.assertEqual(set(sent), {
                    "requestId", "service", "operation", "target", "params",
                    "reason"})
                self.assertEqual(sent["operation"], operation)
                self.assertEqual(sent["target"], target)
                self.assertNotIn("url", sent)
                self.assertNotIn("method", sent)
                self.assertNotIn("token", sent)

    def test_proposal_and_status_tools_use_typed_action_and_get_status(self):
        request_id = "00000000-0000-4000-8000-000000000002"

        def pending_response(request):
            sent = json.loads(request.data)
            return json.dumps({
                "requestId": sent["requestId"], "state": "PENDING"
            }).encode()

        proposal = _Opener(pending_response, status=202)
        result = self.invoke(
            proposal, tool="sonar.propose_accept_issue", target="ISSUE-123",
            project_key="trusted_project_000", reason="owner review",
            request_id=request_id)
        sent = json.loads(proposal.request.data)
        self.assertEqual(result["state"], "PENDING")
        self.assertEqual(proposal.request.get_method(), "POST")
        self.assertTrue(proposal.request.full_url.endswith("/v1/actions"))
        self.assertEqual(sent["operation"], "accept_issue")
        self.assertEqual(sent["target"], "ISSUE-123")
        self.assertEqual(sent["params"], {"projectKey": "trusted_project_000"})
        self.assertEqual(sent["requestId"], request_id)

        status = _Opener(json.dumps({
            "requestId": request_id, "state": "REJECTED"
        }).encode())
        result = self.invoke(
            status, tool="approvals.request_status", request_id=request_id)
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(status.request.get_method(), "GET")
        self.assertTrue(status.request.full_url.endswith(
            "/v1/requests/" + request_id))
        self.assertIsNone(status.request.data)

    def test_proposal_requires_stable_request_id_and_unknown_tools_fail_closed(self):
        with self.assertRaisesRegex(
                Denied, "FORTIS_PROPOSAL_STABLE_REQUEST_ID_REQUIRED"):
            bridge.payload(
                "sonar.propose_accept_issue", target="ISSUE-123",
                project_key="trusted_project_000")
        with self.assertRaisesRegex(Denied, "FORTIS_TOOL_NOT_SUPPORTED"):
            bridge.payload("sonar.delete_project")


if __name__ == "__main__":
    unittest.main()
