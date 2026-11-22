import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings

logger = logging.getLogger(__name__)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class EcodeApiError(Exception):
    def __init__(self, message, status_code=None, raw_response=None):
        super().__init__(message)
        self.status_code = status_code
        self.raw_response = raw_response

class EcodeSyncVerificationError(EcodeApiError):
    """Raised when result sync times out and the outcome on E-Code is uncertain."""
    pass

def ecode_base_url():
    return os.environ.get("ECODE_API_BASE_URL", "https://ecode-backend.onrender.com").rstrip("/")

def sync_secret():
    secret = os.environ.get("CODECLASH_SYNC_SECRET")
    if not secret:
        try:
            key_path = getattr(settings, "DATA", None)
            if key_path:
                secret = (key_path / "ecode-sync.key").read_text().strip()
        except OSError:
            pass
    if not secret:
        raise EcodeApiError("Sync secret is not configured on the LAN server (CODECLASH_SYNC_SECRET or ecode-sync.key).")
    return secret

def _send_request(url, method="GET", data=None, headers=None, timeout=20, max_retries=2):
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    
    encoded_data = None
    if data is not None:
        if isinstance(data, (dict, list)):
            encoded_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            encoded_data = data.encode("utf-8")
        else:
            encoded_data = data

    retries = 0
    while True:
        try:
            request = Request(url, data=encoded_data, headers=req_headers, method=method)
            opener = build_opener(NoRedirect)
            with opener.open(request, timeout=timeout) as response:
                status = response.status
                body = response.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(body)
                except ValueError:
                    raise EcodeApiError(f"Invalid JSON returned by E-Code ({status}): {body[:200]}", status_code=status)
                return payload

        except HTTPError as e:
            status = e.code
            err_body = e.read().decode("utf-8", errors="replace")
            logger.warning("E-Code API HTTP error %s for %s: %s", status, url, err_body[:200])
            if method == "GET" and status in (502, 503, 504) and retries < max_retries:
                retries += 1
                time.sleep(1.0 * retries)
                continue
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message") or err_json.get("error") or f"HTTP {status}"
            except ValueError:
                msg = f"HTTP {status}: {err_body[:200]}"
            raise EcodeApiError(msg, status_code=status, raw_response=err_body)

        except (URLError, TimeoutError, OSError) as e:
            logger.warning("E-Code API network error for %s: %s", url, str(e))
            if method == "POST":
                # For POST requests, network timeout leaves outcome uncertain
                raise EcodeSyncVerificationError(
                    f"Sync request timed out or network lost. Outcome on E-Code is uncertain: {e}"
                ) from e
            if retries < max_retries:
                retries += 1
                time.sleep(1.0 * retries)
                continue
            raise EcodeApiError(f"Network error connecting to E-Code: {e}") from e

def fetch_active_contest(contest_id=None, event_id=None, timeout=20):
    """
    GET /api/v1/codeclash/active-contest
    Optional query params: contestId, eventId
    """
    base = ecode_base_url()
    params = {}
    if contest_id:
        params["contestId"] = contest_id
    if event_id:
        params["eventId"] = event_id
    
    url = f"{base}/api/v1/codeclash/active-contest"
    if params:
        url += f"?{urlencode(params)}"

    payload = _send_request(url, method="GET", timeout=timeout)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        msg = payload.get("message", "E-Code returned unsuccessful status for active-contest")
        raise EcodeApiError(msg)
    
    data = payload.get("data")
    if not isinstance(data, dict):
        raise EcodeApiError("Invalid active-contest response: 'data' object missing.")
    
    # Validate required fields as per new.md
    required_fields = ("contestId", "name", "date", "startTime", "endTime")
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        raise EcodeApiError(f"Active contest response missing required fields: {', '.join(missing)}")
    
    return data

def fetch_roster(timeout=60):
    """
    GET /api/v1/codeclash/roster
    Requires X-CodeClash-Sync-Secret
    """
    base = ecode_base_url()
    secret = sync_secret()
    url = f"{base}/api/v1/codeclash/roster"
    headers = {"X-CodeClash-Sync-Secret": secret}

    payload = _send_request(url, method="GET", headers=headers, timeout=timeout)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        msg = payload.get("message", "E-Code returned unsuccessful status for roster export")
        raise EcodeApiError(msg)
    
    data = payload.get("data")
    if not isinstance(data, dict):
        raise EcodeApiError("Invalid roster response: 'data' object missing.")
    
    roster = data.get("roster")
    total = data.get("totalStudents")
    if not isinstance(roster, list) or len(roster) != total:
        raise EcodeApiError(f"Roster student count mismatch: expected {total}, received {len(roster) if isinstance(roster, list) else 'non-list'}.")
    
    return roster, data

def sync_contest_results(payload_dict, timeout=90):
    """
    POST /api/v1/codeclash/sync
    Requires X-CodeClash-Sync-Secret
    """
    base = ecode_base_url()
    secret = sync_secret()
    url = f"{base}/api/v1/codeclash/sync"
    headers = {"X-CodeClash-Sync-Secret": secret}

    result = _send_request(url, method="POST", data=payload_dict, headers=headers, timeout=timeout, max_retries=0)
    if not isinstance(result, dict) or result.get("success") is not True:
        msg = result.get("message", "E-Code returned unsuccessful status for result sync")
        raise EcodeApiError(msg)
    
    return result

def fetch_contest_leaderboard(contest_id, timeout=15):
    """
    GET /api/v1/codeclash/leaderboards/contests/:contestId
    """
    base = ecode_base_url()
    url = f"{base}/api/v1/codeclash/leaderboards/contests/{contest_id}"
    return _send_request(url, method="GET", timeout=timeout)

def fetch_leaderboards(batch="all", page=1, limit=50, timeout=15):
    """
    GET /api/v1/codeclash/leaderboards?batch=:batch&page=:page&limit=:limit
    """
    base = ecode_base_url()
    params = {"batch": batch, "page": page, "limit": limit}
    url = f"{base}/api/v1/codeclash/leaderboards?{urlencode(params)}"
    return _send_request(url, method="GET", timeout=timeout)
