"""
UiPath Document Understanding API Connector
=============================================
Uses the UiPath Automation Cloud Document Understanding API.

3-step pipeline:
    1. Digitize  — OCR the document, returns documentId
    2. Classify  — detect document type
    3. Extract   — extract fields using the classified type

Credentials from .env:
    UIPATH_CLIENT_ID=...
    UIPATH_CLIENT_SECRET=...
    UIPATH_ORG=qbotibzowkpm
    UIPATH_TENANT=DefaultTenant
"""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

UIPATH_TOKEN_URL = "https://cloud.uipath.com/identity_/connect/token"
POLL_INTERVAL    = 2
MAX_POLL         = 60

SCOPE = "Du.Classification.Api Du.Digitization.Api Du.Extraction.Api"

# Document type mapping
UIPATH_DOCTYPE_MAP = {
    "passport":        "PASSPORT",
    "driver_license":  "DRIVERS_LICENSE",
    "driving_license": "DRIVERS_LICENSE",
    "national_id":     "DRIVERS_LICENSE",
    "id_card":         "DRIVERS_LICENSE",
    "identity":        "GENERIC",
    "invoice":         "INSURANCE",
    "receipt":         "GENERIC",
}


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
        client_id     = os.getenv("UIPATH_CLIENT_ID", "")
        client_secret = os.getenv("UIPATH_CLIENT_SECRET", "")
        org           = os.getenv("UIPATH_ORG", "")
        tenant        = os.getenv("UIPATH_TENANT", "DefaultTenant")
        if not client_id or not client_secret:
            raise UiPathAPIError(
                "UIPATH_CLIENT_ID and UIPATH_CLIENT_SECRET must be set in .env"
            )
        return cls(client_id=client_id, client_secret=client_secret,
                   org=org, tenant=tenant)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        try:
            resp = requests.post(UIPATH_TOKEN_URL, data={
                "grant_type":    "client_credentials",
                "client_id":     self._client_id,
                "client_secret": self._client_secret,
                "scope":         SCOPE,
            }, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise UiPathAPIError(f"UiPath auth failed: {e}")
        data = resp.json()
        if "access_token" not in data:
            raise UiPathAPIError(f"No access_token in response: {data}")
        self._token        = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def test_connection(self) -> bool:
        try:
            return bool(self._get_token())
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Main extraction
    # ------------------------------------------------------------------

    def extract_to_json(self, file_path: str | Path,
                        extractor: str = "identity_documents",
                        output_dir: Optional[str | Path] = None) -> Path:
        """
        Full 3-step extraction: Digitize → Classify → Extract.
        Returns path to the saved JSON file.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        token   = self._get_token()
        headers = {
            "Authorization":       f"Bearer {token}",
            "Content-Type":        "application/json",
            "X-UIPATH-TenantName": self._tenant,
        }

        base_url = f"https://cloud.uipath.com/{self._org}/{self._tenant}/du_/api/framework"

        # Step 1: Get project list
        project_id = self._get_project_id(base_url, headers)
        logger.info("UiPath project_id: %s", project_id)

        # Step 2: Digitize
        doc_id = self._digitize(base_url, headers, project_id, file_path)
        logger.info("UiPath doc_id: %s", doc_id)

        # Step 3: Classify
        doc_type_id, extractor_id = self._classify(base_url, headers, project_id, doc_id)
        logger.info("UiPath classified as: %s extractor: %s", doc_type_id, extractor_id)

        # Step 4: Extract
        raw_result = self._extract(base_url, headers, project_id, doc_id, extractor_id)

        # Convert to pipeline JSON format
        pipeline_json = self._convert(raw_result, file_path.name, doc_type_id)

        # Save
        out_dir = Path(output_dir) if output_dir else file_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (file_path.stem + "_uipath.json")
        out_path.write_text(json.dumps(pipeline_json, indent=2))
        logger.info("Saved UiPath result: %s", out_path)
        return out_path

    def extract_raw(self, file_path: str | Path,
                    extractor: str = "identity_documents") -> dict:
        return {}

    # ------------------------------------------------------------------
    # Private steps
    # ------------------------------------------------------------------

    def _get_project_id(self, base_url: str, headers: dict) -> str:
        """Get the first available DU project ID."""
        resp = requests.get(
            f"{base_url}/projects?api-version=1",
            headers={**headers, "Accept": "application/json"},
            timeout=20,
            allow_redirects=False,
        )
        if resp.status_code == 404:
            raise UiPathAPIError(
                "Document Understanding service is not enabled in your UiPath tenant. "
                "Go to cloud.uipath.com → Admin → Tenants → DefaultTenant → Services → "
                "Enable 'Document Understanding', then try again."
            )
        if resp.status_code == 200 and "application/json" in resp.headers.get("Content-Type", ""):
            data = resp.json()
            projects = data.get("projects") or data.get("value") or (data if isinstance(data, list) else [])
            if projects:
                return projects[0].get("id") or projects[0].get("projectId", "")
        # Fallback: try "default" project
        return "default"

    def _digitize(self, base_url: str, headers: dict,
                  project_id: str, file_path: Path) -> str:
        """Step 1: Upload document for OCR, get a documentId back."""
        suffix = file_path.suffix.lower()
        mime   = {
            ".pdf":  "application/pdf",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
        }.get(suffix, "application/octet-stream")

        content_b64 = base64.b64encode(file_path.read_bytes()).decode()

        url = f"{base_url}/projects/{project_id}/digitization/start?api-version=1"
        payload = {
            "contentType": mime,
            "content":     content_b64,
        }

        resp = requests.post(url, headers={**headers, "Accept": "application/json"},
                             json=payload, timeout=60)
        if resp.status_code in (200, 202) and "application/json" in ct:
            data = resp.json()
            doc_id = data.get("documentId") or data.get("id") or ""
            if doc_id:
                return doc_id
            # Async: poll
            op_id = data.get("operationId", "")
            if op_id:
                return self._poll_digitization(base_url, headers, project_id, op_id)
        raise UiPathAPIError(
            f"Digitization failed ({resp.status_code}). "
            f"The Document Understanding service may not be enabled in your tenant. "
            f"Go to: cloud.uipath.com → Admin → Tenants → DefaultTenant → Services → Enable Document Understanding. "
            f"Response: {resp.text[:100]}"
        )

    def _poll_digitization(self, base_url: str, headers: dict,
                           project_id: str, op_id: str) -> str:
        url = f"{base_url}/projects/{project_id}/digitization/{op_id}/result?api-version=1"
        for _ in range(MAX_POLL):
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.ok:
                data = resp.json()
                if data.get("status", "").lower() == "succeeded":
                    return data.get("documentId", "")
            time.sleep(POLL_INTERVAL)
        raise UiPathAPIError("Digitization timed out")

    def _classify(self, base_url: str, headers: dict,
                  project_id: str, doc_id: str) -> tuple[str, str]:
        """Step 2: Classify the document, returns (doc_type_id, extractor_id)."""
        url = f"{base_url}/projects/{project_id}/classifiers/ml-classification/classification/start?api-version=1"
        payload = {"documentId": doc_id}

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code in (200, 202):
            data = resp.json()
            doc_type_id  = data.get("documentTypeId", "identity")
            extractor_id = data.get("extractorId", "ml-extractor")
            if data.get("operationId"):
                doc_type_id, extractor_id = self._poll_classification(
                    base_url, headers, project_id, data["operationId"]
                )
            return doc_type_id, extractor_id

        # If classification endpoint doesn't exist, use default extractor
        logger.warning("Classification unavailable (%s), using generative_extractor", resp.status_code)
        return "identity", "generative_extractor"

    def _poll_classification(self, base_url: str, headers: dict,
                             project_id: str, op_id: str) -> tuple[str, str]:
        url = f"{base_url}/projects/{project_id}/classifiers/ml-classification/classification/{op_id}/result?api-version=1"
        for _ in range(MAX_POLL):
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.ok:
                data = resp.json()
                if data.get("status", "").lower() == "succeeded":
                    results = data.get("classificationResults", [{}])
                    best    = results[0] if results else {}
                    return best.get("documentTypeId", "identity"), best.get("extractorId", "ml-extractor")
            time.sleep(POLL_INTERVAL)
        return "identity", "ml-extractor"

    def _extract(self, base_url: str, headers: dict,
                 project_id: str, doc_id: str, extractor_id: str) -> dict:
        """Step 3: Extract fields using the classified extractor."""
        # Try generative extractor first (most capable for identity docs)
        for ext_id in [extractor_id, "generative_extractor", "ml-extractor"]:
            url = f"{base_url}/projects/{project_id}/extractors/{ext_id}/extraction?api-version=1"
            payload = {"documentId": doc_id}
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code in (200, 202):
                data = resp.json()
                if data.get("operationId"):
                    return self._poll_extraction(base_url, headers, project_id, ext_id, data["operationId"])
                return data
            elif resp.status_code == 404:
                continue
            else:
                logger.warning("Extraction %s: %s %s", ext_id, resp.status_code, resp.text[:200])

        raise UiPathAPIError("All extractors failed")

    def _poll_extraction(self, base_url: str, headers: dict,
                         project_id: str, extractor_id: str, op_id: str) -> dict:
        url = f"{base_url}/projects/{project_id}/extractors/{extractor_id}/extraction/{op_id}/result?api-version=1"
        for _ in range(MAX_POLL):
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.ok:
                data = resp.json()
                if data.get("status", "").lower() == "succeeded":
                    return data
            time.sleep(POLL_INTERVAL)
        raise UiPathAPIError("Extraction timed out")

    # ------------------------------------------------------------------
    # Convert UiPath response → pipeline JSON format
    # ------------------------------------------------------------------

    def _convert(self, raw: dict, source_file: str, doc_type_id: str) -> dict:
        """Convert UiPath extraction result to your pipeline's JSON format."""
        doc_type = UIPATH_DOCTYPE_MAP.get(doc_type_id.lower().replace(" ", "_"), "GENERIC")

        # UiPath extraction result fields
        fields_raw = (
            raw.get("extractionResult", {}).get("fieldsValue")
            or raw.get("extractionResult", {}).get("fields")
            or raw.get("fieldsValue")
            or raw.get("fields")
            or {}
        )

        confidence = float(raw.get("confidence", 1.0))

        # Normalize field names
        name_map = {
            "surname":        "name",
            "given_names":    "name",
            "givenname":      "name",
            "fullname":       "name",
            "full_name":      "name",
            "dateofbirth":    "dob",
            "date_of_birth":  "dob",
            "birthdate":      "dob",
            "documentnumber": "passport_number",
            "licensenumber":  "license_number",
            "expirydate":     "expiry_date",
            "issuedate":      "issue_date",
        }

        fields: dict = {}
        for raw_key, raw_val in fields_raw.items():
            norm = name_map.get(raw_key.lower().replace(" ", "_"), raw_key.lower())
            if isinstance(raw_val, dict):
                val  = raw_val.get("value")
                conf = float(raw_val.get("confidence", confidence))
                bbox = raw_val.get("boundingBox") or raw_val.get("ocr_box") or [0, 0, 0, 0]
            else:
                val, conf, bbox = str(raw_val) if raw_val else None, confidence, [0,0,0,0]
            if val is not None and str(val).strip():
                if isinstance(bbox, dict):
                    bbox = [int(bbox.get("left",0)), int(bbox.get("top",0)),
                            int(bbox.get("right",0)), int(bbox.get("bottom",0))]
                fields[norm] = {
                    "value":        str(val).strip(),
                    "confidence":   round(min(1.0, max(0.0, conf)), 3),
                    "page":         1,
                    "bounding_box": bbox if isinstance(bbox, list) else [0,0,0,0],
                }

        return {
            "document_type": doc_type,
            "confidence":    round(confidence, 3),
            "source_file":   source_file,
            "fields":        fields,
        }
