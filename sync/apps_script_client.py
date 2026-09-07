"""
Google Apps Script Web App Client for Pedne Sewa Trust - Employment Registry.
Transfers candidate backups directly to a secure, private Google Sheet gateway
via HTTPS POST without requiring desktop Google OAuth or credentials files.
"""

import os
from typing import List, Dict, Any, Optional
import requests
from app.config import config
from app.constants import DEFAULT_SPREADSHEET_ID
from models.candidate import Candidate
from models.visitor import VisitorRecord
from utils.logger import logger


class AppsScriptClient:
    """Client for pushing candidate backups to a Google Apps Script Web App endpoint."""

    def __init__(self):
        pass

    def get_endpoint_url(self) -> str:
        """Returns the configured Google Apps Script Web App URL from env or config."""
        url = os.environ.get("GOOGLE_APPS_SCRIPT_URL") or config.get("apps_script_url") or ""
        return url.strip()

    def get_api_key(self) -> str:
        """Returns the configured backup API key from env or config without logging it."""
        key = os.environ.get("BACKUP_API_KEY") or config.get("backup_api_key") or config.get("api_key") or ""
        return key.strip()

    def is_configured(self) -> bool:
        """
        Validates if both a valid Google Apps Script Web App URL and API key are configured.
        Returns False if blank or if using the unconfigured placeholder.
        """
        url = self.get_endpoint_url()
        key = self.get_api_key()
        if not url or not key:
            return False
        if "YOUR_DEPLOYMENT_ID" in url:
            return False
        return url.startswith("https://script.google.com/")

    def push_candidates(self, candidates: List[Candidate]) -> Dict[str, Any]:
        """
        Sends candidate records to the Google Apps Script Web App endpoint.
        Maintains backwards compatibility with existing callers.
        """
        return self.push_backup(candidates=candidates)

    def push_backup(
        self,
        candidates: Optional[List[Candidate]] = None,
        visitors: Optional[List[VisitorRecord]] = None
    ) -> Dict[str, Any]:
        """
        Sends both Candidate records and Visiting Register records to the Google Apps Script Web App.
        Returns a dict indicating SUCCESS or FAILURE with status details.
        """
        if not self.is_configured():
            url = self.get_endpoint_url()
            key = self.get_api_key()
            if not url or "YOUR_DEPLOYMENT_ID" in url:
                msg = "Google Apps Script backup endpoint URL is not configured."
            elif not key:
                msg = "Google Apps Script backup API key is not configured (BACKUP_API_KEY)."
            else:
                msg = "Google Apps Script backup gateway is not configured properly."
            logger.warning(msg)
            return {"status": "NOT_CONFIGURED", "records_pushed": 0, "error": msg}

        cands = candidates or []
        vis = visitors or []
        total_records = len(cands) + len(vis)

        if total_records == 0:
            return {"status": "SUCCESS", "records_pushed": 0, "message": "No records to sync."}

        url = self.get_endpoint_url()
        api_key = self.get_api_key()

        # Strict contract: api_key, candidates array, and visitors array
        payload = {
            "api_key": api_key,
            "candidates": [c.to_backup_dict() for c in cands],
            "visitors": [v.to_backup_dict() for v in vis]
        }

        try:
            logger.info(
                "Sending %d candidate and %d visitor records to Google Apps Script gateway...",
                len(cands), len(vis)
            )
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=45,
                allow_redirects=True
            )

            # Check redirect history for Google Login redirection
            all_urls = [r.url for r in response.history] + [response.url]
            for u in all_urls:
                if "accounts.google.com" in u:
                    err = "Apps Script deployment redirected to Google Login. Ensure Web App deployment 'Who has access' is set to 'Anyone'."
                    logger.error(err)
                    return {"status": "FAILURE", "records_pushed": 0, "error": err}

            # Check HTTP status code
            if response.status_code != 200:
                err = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error("Apps Script gateway returned HTTP %d: %s", response.status_code, response.text[:200])
                return {"status": "FAILURE", "records_pushed": 0, "error": err}

            # Check for HTML responses (e.g., error pages, permission dialogs)
            resp_text = response.text.strip()
            if resp_text.startswith("<") or "<html" in resp_text.lower():
                err = "Received unexpected HTML response instead of JSON. Verify Apps Script deployment."
                logger.error("Apps Script returned HTML body: %s", resp_text[:250])
                return {"status": "FAILURE", "records_pushed": 0, "error": err}

            # Strict JSON parsing: must not fallback to SUCCESS if invalid JSON
            try:
                res_json = response.json()
            except Exception as parse_err:
                err = f"Malformed JSON response from Apps Script: {parse_err}"
                logger.error("%s (Response: %s)", err, resp_text[:250])
                return {"status": "FAILURE", "records_pushed": 0, "error": err}

            # Outdated deployment detection:
            # If we sent visitors, but Apps Script returned "Nothing to backup" or 0 processed without visitor details,
            # it means the live Apps Script deployment in Google Cloud has not been updated with the Visiting Register code.
            inserted = res_json.get("records_inserted", res_json.get("inserted", 0))
            updated = res_json.get("records_updated", res_json.get("updated", 0))
            processed = res_json.get("records_processed", res_json.get("processed", 0))

            if len(vis) > 0:
                msg_str = str(res_json.get("message", "")).lower()
                has_visitor_details = "visitors" in res_json or ("details" in res_json and "visitors" in res_json["details"])
                if "nothing to backup" in msg_str or (processed == 0 and not has_visitor_details):
                    err = (
                        "Google Apps Script requires update in Google Sheets! "
                        "The live web app is running an older deployment that does not support the Visiting Register. "
                        "Please copy code from sync/google_apps_script.js into Extensions -> Apps Script -> Deploy -> Manage deployments -> New version."
                    )
                    logger.error(err)
                    return {"status": "FAILURE", "records_pushed": 0, "error": err}

            # Validate success: accept status == "SUCCESS" or success == True
            is_success = (res_json.get("status") == "SUCCESS") or (res_json.get("success") is True)
            if is_success:
                logger.info(
                    "Apps Script backup succeeded: %d processed (%d inserted, %d updated).",
                    processed, inserted, updated
                )
                return {
                    "status": "SUCCESS",
                    "records_pushed": total_records,
                    "candidates_pushed": len(cands),
                    "visitors_pushed": len(vis),
                    "records_inserted": inserted,
                    "records_updated": updated,
                    "details": res_json
                }
            else:
                err = res_json.get("message", res_json.get("error", "Apps Script returned non-success status."))
                logger.error("Apps Script reported failure: %s", err)
                return {"status": "FAILURE", "records_pushed": 0, "error": err}


        except requests.exceptions.Timeout:
            err = "Connection timed out while contacting cloud backup gateway. Data is safely stored locally."
            logger.warning(err)
            return {"status": "FAILURE", "records_pushed": 0, "error": err}
        except requests.exceptions.RequestException as e:
            err = f"Network communication error: {e}. Data safely retained locally."
            logger.warning(err)
            return {"status": "FAILURE", "records_pushed": 0, "error": err}
        except Exception as e:
            err = f"Unexpected error during backup transmission: {e}"
            logger.error(err)
            return {"status": "FAILURE", "records_pushed": 0, "error": err}


apps_script_client = AppsScriptClient()
