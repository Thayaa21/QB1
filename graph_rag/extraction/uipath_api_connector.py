"""
UiPath Document Understanding API Connector
============================================
Uses the Automation Cloud DU API.
Pipeline: Digitize (multipart/form-data) → Extract (generative extractor with prompts)

.env:
    UIPATH_CLIENT_ID=...
    UIPATH_CLIENT_SECRET=...
    UIPATH_ORG=qbotibzowkpm
    UIPATH_TENANT=DefaultTenant
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

UIPATH_TOKEN_URL   = "https://cloud.uipath.com/identity_/connect/token"
UIPATH_SCOPE       = "Du.Classification.Api Du.Digitization.Api Du.Extraction.Api"
PREDEFINED_PROJECT = "00000000-0000-0000-0000-000000000000"
POLL_INTERVAL      = 3
MAX_POLL           = 40

UIPATH_DOCTYPE_MAP = {
    "passport":       "PASSPORT",
    "driver_license": "DRIVERS_LICENSE",
    "id_card":        "DRIVERS_LICENSE",
    "identity":       "GENERIC",
    "invoice":        "INSURANCE",
}

# Questions to ask the generative extractor
EXTRACTION_PROMPTS = [
    {"id": "name",            "question": "What is the full name of the person on this document?"},
    {"id": "dob",             "question": "What is the date of birth?"},
    {"id": "license_number",  "question": "What is the driver license number or document ID number?"},
    {"id": "passport_number", "question": "What is the passport number?"},
    {"id": "expiry_date",     "question": "What is the expiry or expiration date?"},
    {"id": "issue_date",      "question": "What is the issue date?"},
    {"id": "address",         "question": "What is the full address?"},
    {"id": "place_of_birth",  "question": "What is the place of birth?"},
    {"id": "nationality",     "question": "What is the nationality or citizenship?"},
    {"id": "class",           "question": "What is the license class or vehicle class?"},
    {"id": "sex",             "question": "What is the sex or gender (M or F)?"},
    {"id": "height",          "question": "What is the height?"},
]


class UiPathAPIError(Exception):
    pass


class UiPathAPIConnector:

    def __init__(self, client_id: str, client_secret: str,
                 org: str = "", tenant: str = "DefaultTenant"):
        self._client_id     = client_id
        self._client_secret = client_secret
        self._org           = org
        self._tenant        = tenant
        self._token:        Optional[str] = None
        self._token_expiry: float = 0.0

    @classmethod
    def from_env(cls) -> "UiPathAPIConnector":
        cid = os.getenv("UIPATH_CLIENT_ID", "")
        cs  = os.getenv("UIPATH_CLIENT_SECRET", "")
        if not cid or not cs:
            raise UiPathAPIError("UIPATH_CLIENT_ID and UIPATH_CLIENT_SECRET must be set in .env")
        return cls(cid, cs,
                   org=os.getenv("UIPATH_ORG", ""),
                   tenant=os.getenv("UIPATH_TENANT", "DefaultTenant"))

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = requests.post(UIPATH_TOKEN_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
            "scope":         UIPATH_SCOPE,
        }, timeout=30)
        if not resp.ok:
            raise UiPathAPIError(f"Auth failed ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        if "access_token" not in data:
            raise UiPathAPIError(f"No access_token: {data}")
        self._token        = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization":       f"Bearer {self._get_token()}",
            "Accept":              "application/json",
            "X-UIPATH-TenantName": self._tenant,
        }

    def _base(self) -> str:
        return f"https://cloud.uipath.com/{self._org}/{self._tenant}/du_/api/framework"

    def test_connection(self) -> bool:
        try:
            return bool(self._get_token())
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Main public method
    # ------------------------------------------------------------------

    def extract_to_json(self, file_path: "str | Path",
                        extractor: str = "identity_documents",
                        output_dir: "Optional[str | Path]" = None) -> Path:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Not found: {file_path}")

        base    = self._base()
        headers = self._headers()

        project_id = self._get_project_id(base, headers)
        doc_id     = self._digitize(base, headers, project_id, file_path)
        raw        = self._extract(base, headers, project_id, doc_id)
        pipeline   = self._convert(raw, file_path.name)

        out_dir  = Path(output_dir) if output_dir else file_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (file_path.stem + "_uipath.json")
        out_path.write_text(json.dumps(pipeline, indent=2))
        logger.info("Saved UiPath result: %s", out_path)
        return out_path

    def extract_raw(self, file_path: "str | Path",
                    extractor: str = "identity_documents") -> dict:
        return {}

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _get_project_id(self, base: str, headers: dict) -> str:
        resp = requests.get(f"{base}/projects?api-version=1",
                            headers=headers, timeout=20, allow_redirects=False)
        if resp.status_code == 404:
            raise UiPathAPIError(
                "Document Understanding not enabled. "
                "Go to cloud.uipath.com → Admin → DefaultTenant → Services → "
                "Enable Document Understanding."
            )
        if resp.ok and "application/json" in resp.headers.get("Content-Type", ""):
            projects = resp.json().get("projects", [])
            if projects:
                return projects[0].get("id", PREDEFINED_PROJECT)
        return PREDEFINED_PROJECT

    def _digitize(self, base: str, headers: dict,
                  project_id: str, file_path: Path) -> str:
        """Upload document via multipart/form-data → return documentId."""
        mime = {".pdf": "application/pdf", ".png": "image/png",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".tiff": "image/tiff"}.get(file_path.suffix.lower(), "application/octet-stream")

        url = f"{base}/projects/{project_id}/digitization/start?api-version=1"
        upload_h = {"Authorization": headers["Authorization"],
                    "Accept": "application/json",
                    "X-UIPATH-TenantName": self._tenant}

        with open(file_path, "rb") as fh:
            resp = requests.post(url, headers=upload_h,
                                 files={"File": (file_path.name, fh, mime)},
                                 timeout=60)

        if not resp.ok:
            raise UiPathAPIError(f"Digitize failed ({resp.status_code}): {resp.text[:200]}")
        if "application/json" not in resp.headers.get("Content-Type", ""):
            raise UiPathAPIError(f"Digitize non-JSON ({resp.status_code}): {resp.text[:200]}")

        data   = resp.json()
        doc_id = data.get("documentId") or data.get("id", "")
        if doc_id:
            return doc_id

        result_url = data.get("resultUrl", "")
        if result_url:
            return self._poll_for_doc_id(result_url, upload_h)

        raise UiPathAPIError(f"No documentId in digitize response: {data}")

    def _poll_for_doc_id(self, result_url: str, headers: dict) -> str:
        for _ in range(MAX_POLL):
            resp = requests.get(result_url, headers=headers, timeout=20)
            if resp.ok and "application/json" in resp.headers.get("Content-Type", ""):
                data   = resp.json()
                status = data.get("status", "").lower()
                if status in ("succeeded", "completed", ""):
                    doc_id = data.get("documentId") or data.get("id", "")
                    if doc_id:
                        return doc_id
                elif status in ("failed", "error"):
                    raise UiPathAPIError(f"Digitization failed: {data}")
            time.sleep(POLL_INTERVAL)
        raise UiPathAPIError("Digitization timed out")

    def _extract(self, base: str, headers: dict,
                 project_id: str, doc_id: str) -> dict:
        """Call generative extractor with question prompts."""
        url     = f"{base}/projects/{project_id}/extractors/generative_extractor/extraction?api-version=1"
        payload = {"documentId": doc_id, "prompts": EXTRACTION_PROMPTS}

        resp = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                             json=payload, timeout=120)
        if not resp.ok:
            raise UiPathAPIError(f"Extraction failed ({resp.status_code}): {resp.text[:300]}")
        if "application/json" not in resp.headers.get("Content-Type", ""):
            raise UiPathAPIError(f"Extraction non-JSON response")

        data = resp.json()
        if data.get("operationId"):
            return self._poll_extraction(base, headers, project_id, data["operationId"])
        return data

    def _poll_extraction(self, base: str, headers: dict,
                         project_id: str, op_id: str) -> dict:
        url = f"{base}/projects/{project_id}/extractors/generative_extractor/extraction/{op_id}/result?api-version=1"
        for _ in range(MAX_POLL):
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.ok and "application/json" in resp.headers.get("Content-Type", ""):
                data   = resp.json()
                status = data.get("status", "").lower()
                if status in ("succeeded", "completed", ""):
                    return data
                elif status in ("failed", "error"):
                    raise UiPathAPIError(f"Extraction failed: {data}")
            time.sleep(POLL_INTERVAL)
        raise UiPathAPIError("Extraction timed out")

    # ------------------------------------------------------------------
    # Convert response to pipeline JSON format
    # ------------------------------------------------------------------

    def _convert(self, raw: dict, source_file: str) -> dict:
        """
        Convert generative extractor response to pipeline JSON format.
        The response has: extractionResult.ResultsDocument.Fields (list)
        where each field has FieldId and Values[0].Value
        """
        extraction  = raw.get("extractionResult", raw)
        results_doc = extraction.get("ResultsDocument", {}) or {}
        fields_list = results_doc.get("Fields", [])
        doc_type_id = results_doc.get("DocumentTypeId", "identity")

        fields: dict = {}
        for field in fields_list:
            field_id   = field.get("FieldId", "").lower()
            is_missing = field.get("IsMissing", True)
            values     = field.get("Values", [])
            if is_missing or not values:
                continue
            val  = str(values[0].get("Value", "")).strip()
            conf = float(values[0].get("Confidence", 1.0))
            if val:
                fields[field_id] = {
                    "value":        val,
                    "confidence":   round(min(1.0, max(0.0, conf)), 3),
                    "page":         1,
                    "bounding_box": [0, 0, 0, 0],
                }

        # Fix name: UiPath returns "KANAGARAJ THAYAANANTHAN" (SURNAME GIVEN)
        # → reorder to "Thayaananthan Kanagaraj" (GIVEN SURNAME)
        if "name" in fields:
            parts = fields["name"]["value"].strip().split()
            if len(parts) == 2 and parts[0].isupper() and parts[1].isupper():
                fields["name"]["value"] = f"{parts[1].title()} {parts[0].title()}"
            elif fields["name"]["value"].isupper():
                fields["name"]["value"] = fields["name"]["value"].title()

        doc_type = UIPATH_DOCTYPE_MAP.get(
            str(doc_type_id).lower().replace(" ", "_"), "GENERIC"
        )

        return {
            "document_type": doc_type,
            "confidence":    1.0,
            "source_file":   source_file,
            "fields":        fields,
        }
