"""
UiPath Document Understanding API Connector
=============================================
Connects to the live UiPath Document Understanding API at du.uipath.com.
Sends a real scanned PDF/image, gets back structured fields + confidence scores,
then converts the response into your existing JSON format so UiPathExtractor
can process it exactly as it does with the synthetic dataset files.

HOW TO USE
----------
1. Sign up free at https://cloud.uipath.com
2. Go to Admin → External Applications → Add Application
3. Scope: Du.DocumentProcessing.API
4. Copy client_id + client_secret into your .env file:

   UIPATH_CLIENT_ID=your_client_id
   UIPATH_CLIENT_SECRET=your_client_secret
   UIPATH_ORG=your_organization_name

5. Then use it:

   connector = UiPathAPIConnector.from_env()
   json_path = connector.extract_to_json("scanned_passport.pdf")
   doc, entities = UiPathExtractor().extract(json_path)

SUPPORTED DOCUMENT TYPES (public pre-trained endpoints)
---------------------------------------------------------
identity_documents  — passports, national IDs, driver licenses
invoices            — invoices and bills
receipts            — store receipts
contracts           — contract documents

MAP TO YOUR DocType
-------------------
The connector auto-maps UiPath's response to your DocType enum.
"""

import base64
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UiPath API constants
# ---------------------------------------------------------------------------

UIPATH_TOKEN_URL = "https://cloud.uipath.com/identity_/connect/token"
UIPATH_BASE_URL  = "https://du.uipath.com"

# Pre-trained public endpoints — no tenant needed
EXTRACTOR_ENDPOINTS = {
    "identity_documents": f"{UIPATH_BASE_URL}/ie/identity_documents",
    "invoices":           f"{UIPATH_BASE_URL}/ie/invoices",
    "receipts":           f"{UIPATH_BASE_URL}/ie/receipts",
    "contracts":          f"{UIPATH_BASE_URL}/ie/contracts",
}

# Map UiPath document sub-types to your DocType values
UIPATH_SUBTYPE_MAP = {
    "passport":        "PASSPORT",
    "national_id":     "DRIVERS_LICENSE",
    "driver_license":  "DRIVERS_LICENSE",
    "driving_license": "DRIVERS_LICENSE",
    "id_card":         "DRIVERS_LICENSE",
    "invoice":         "INSURANCE",        # closest match
    "receipt":         "GENERIC",
    "contract":        "GENERIC",
    # identity_documents default
    "identity":        "GENERIC",
}

# How long to wait for async extraction results (seconds)
MAX_POLL_SECONDS = 120
POLL_INTERVAL    = 2


class UiPathAPIError(Exception):
    """Raised when the UiPath API returns an error."""
    pass


class UiPathAPIConnector:
    """
    Connects to the UiPath Document Understanding public API.

    Authenticates with OAuth2 client credentials, sends a document,
    and returns the extracted fields in your pipeline's JSON format.

    Usage:
        connector = UiPathAPIConnector(client_id="...", client_secret="...")

        # Extract from a PDF file
        json_path = connector.extract_to_json(
            file_path = "scanned_passport.pdf",
            extractor = "identity_documents",  # auto-detected if not given
        )

        # Then feed into your pipeline
        from graph_rag.extraction.uipath_extractor import UiPathExtractor
        doc, entities = UiPathExtractor().extract(json_path)
    """

    def __init__(
        self,
        client_id:     str,
        client_secret: str,
        org_name:      str = "",
    ):
        """
        Args:
            client_id     — from UiPath External Applications
            client_secret — from UiPath External Applications
            org_name      — your UiPath organization name (optional for public endpoints)
        """
        self._client_id     = client_id
        self._client_secret = client_secret
        self._org_name      = org_name
        self._token:        Optional[str] = None
        self._token_expiry: float = 0.0

    @classmethod
    def from_env(cls) -> "UiPathAPIConnector":
        """
        Create connector from environment variables.

        Required in .env:
            UIPATH_CLIENT_ID=...
            UIPATH_CLIENT_SECRET=...

        Optional:
            UIPATH_ORG=...  (your organization name)
        """
        client_id     = os.getenv("UIPATH_CLIENT_ID", "")
        client_secret = os.getenv("UIPATH_CLIENT_SECRET", "")
        org_name      = os.getenv("UIPATH_ORG", "")

        if not client_id or not client_secret:
            raise UiPathAPIError(
                "UIPATH_CLIENT_ID and UIPATH_CLIENT_SECRET must be set in .env\n"
                "Get them from: cloud.uipath.com → Admin → External Applications"
            )

        return cls(client_id=client_id, client_secret=client_secret, org_name=org_name)

    # ------------------------------------------------------------------
    # Main method: extract a document → return JSON file path
    # ------------------------------------------------------------------

    def extract_to_json(
        self,
        file_path: str | Path,
        extractor: str = "identity_documents",
        output_dir: Optional[str | Path] = None,
    ) -> Path:
        """
        Extract fields from a document using the UiPath API.

        Sends the file to UiPath's pre-trained model, waits for results,
        then saves a JSON file in your pipeline's format.

        Args:
            file_path  — path to PDF, PNG, JPG, or TIFF file
            extractor  — which pre-trained model to use:
                         "identity_documents" (passports, licenses, IDs)
                         "invoices", "receipts", "contracts"
            output_dir — where to save the output JSON (default: same dir as input)

        Returns:
            Path to the generated .json file

        Raises:
            UiPathAPIError — on API failures
            FileNotFoundError — if file_path doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("UiPath API: extracting %s using %s", file_path.name, extractor)

        # Step 1: Get auth token
        token = self._get_token()

        # Step 2: Encode file as base64
        content_type, content_b64 = self._encode_file(file_path)

        # Step 3: Call extraction endpoint
        endpoint = EXTRACTOR_ENDPOINTS.get(extractor)
        if not endpoint:
            raise UiPathAPIError(
                f"Unknown extractor: {extractor!r}. "
                f"Choose from: {list(EXTRACTOR_ENDPOINTS.keys())}"
            )

        raw_result = self._call_extraction_api(token, endpoint, content_type, content_b64)

        # Step 4: Convert to your JSON format
        pipeline_json = self._convert_to_pipeline_format(raw_result, file_path.name, extractor)

        # Step 5: Save JSON file
        if output_dir is None:
            output_dir = file_path.parent
        output_path = Path(output_dir) / (file_path.stem + "_uipath.json")
        output_path.write_text(json.dumps(pipeline_json, indent=2), encoding="utf-8")

        logger.info("UiPath API: saved result to %s", output_path)
        return output_path

    def extract_raw(
        self,
        file_path: str | Path,
        extractor: str = "identity_documents",
    ) -> dict:
        """
        Extract and return the raw UiPath API response (not converted).
        Useful for debugging or inspecting the full response.
        """
        file_path = Path(file_path)
        token = self._get_token()
        content_type, content_b64 = self._encode_file(file_path)
        endpoint = EXTRACTOR_ENDPOINTS.get(extractor, EXTRACTOR_ENDPOINTS["identity_documents"])
        return self._call_extraction_api(token, endpoint, content_type, content_b64)

    def test_connection(self) -> bool:
        """
        Test if credentials are valid and API is reachable.
        Returns True on success, False on failure.
        """
        try:
            token = self._get_token()
            return bool(token)
        except Exception as e:
            logger.warning("UiPath connection test failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Private: Authentication
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """
        Get a valid OAuth2 Bearer token.
        Caches the token and refreshes it when expired.

        UiPath uses OAuth2 Client Credentials flow:
        - You send client_id + client_secret
        - You get back an access_token + expires_in
        - Use the access_token as: Authorization: Bearer <token>
        """
        # Return cached token if still valid (with 60s buffer)
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        logger.debug("UiPath API: requesting new token")

        try:
            response = requests.post(
                UIPATH_TOKEN_URL,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                    "scope":         "Du.DocumentProcessing.API",
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise UiPathAPIError(
                "Cannot connect to UiPath identity service. Check your internet connection."
            )
        except requests.exceptions.HTTPError as e:
            raise UiPathAPIError(
                f"UiPath authentication failed: {e}. "
                f"Check your UIPATH_CLIENT_ID and UIPATH_CLIENT_SECRET."
            )

        data = response.json()
        if "access_token" not in data:
            raise UiPathAPIError(
                f"UiPath token response missing access_token: {data}"
            )

        self._token        = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        logger.debug("UiPath API: token acquired, expires in %ds", data.get("expires_in", 3600))

        return self._token

    # ------------------------------------------------------------------
    # Private: File encoding
    # ------------------------------------------------------------------

    def _encode_file(self, file_path: Path) -> tuple[str, str]:
        """
        Read a file and encode it as base64 for the API.
        Returns (content_type, base64_string).
        """
        suffix = file_path.suffix.lower()
        content_type_map = {
            ".pdf":  "application/pdf",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif":  "image/tiff",
        }
        content_type = content_type_map.get(suffix, "application/octet-stream")

        with open(file_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        logger.debug(
            "Encoded file: %s (%s, %d bytes base64)",
            file_path.name, content_type, len(content_b64)
        )
        return content_type, content_b64

    # ------------------------------------------------------------------
    # Private: API call
    # ------------------------------------------------------------------

    def _call_extraction_api(
        self,
        token: str,
        endpoint: str,
        content_type: str,
        content_b64: str,
    ) -> dict:
        """
        Call the UiPath extraction endpoint and return the result.

        UiPath extraction is asynchronous:
        1. POST to start extraction → get an operationId
        2. GET to poll for result → wait until status = "Succeeded"

        For simple synchronous calls (smaller docs), the result may come
        back in the initial response.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        payload = {
            "contentType": content_type,
            "content":     content_b64,
        }

        # Try synchronous endpoint first (simpler)
        sync_url = f"{endpoint}/extraction"
        try:
            response = requests.post(sync_url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                return response.json()

            # 202 = accepted (async) — poll for result
            if response.status_code == 202:
                operation_id = response.json().get("operationId")
                if operation_id:
                    return self._poll_for_result(token, endpoint, operation_id)

            # Other error
            response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            raise UiPathAPIError(
                f"UiPath extraction API error: {e}. "
                f"Response: {response.text[:200]}"
            )
        except requests.exceptions.Timeout:
            raise UiPathAPIError("UiPath extraction API timed out after 60s.")
        except requests.exceptions.ConnectionError:
            raise UiPathAPIError(
                f"Cannot reach UiPath API at {endpoint}. Check internet connection."
            )

        return response.json()

    def _poll_for_result(
        self, token: str, endpoint: str, operation_id: str
    ) -> dict:
        """
        Poll UiPath for an async extraction result.
        Polls every POLL_INTERVAL seconds up to MAX_POLL_SECONDS.
        """
        headers = {"Authorization": f"Bearer {token}"}
        status_url = f"{endpoint}/extraction/{operation_id}"

        start = time.time()
        while time.time() - start < MAX_POLL_SECONDS:
            try:
                response = requests.get(status_url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()

                status = data.get("status", "").lower()
                if status == "succeeded":
                    return data
                elif status in ("failed", "error"):
                    raise UiPathAPIError(
                        f"UiPath extraction failed: {data.get('error', 'unknown error')}"
                    )

                logger.debug("UiPath polling: status=%s, waiting...", status)
                time.sleep(POLL_INTERVAL)

            except requests.exceptions.RequestException as e:
                raise UiPathAPIError(f"UiPath polling error: {e}")

        raise UiPathAPIError(
            f"UiPath extraction timed out after {MAX_POLL_SECONDS}s. "
            f"Operation ID: {operation_id}"
        )

    # ------------------------------------------------------------------
    # Private: Response conversion
    # ------------------------------------------------------------------

    def _convert_to_pipeline_format(
        self, raw: dict, source_file: str, extractor: str
    ) -> dict:
        """
        Convert UiPath API response to your pipeline's JSON format.

        Your pipeline expects:
        {
          "document_type": "PASSPORT",
          "confidence": 0.97,
          "source_file": "scan.pdf",
          "fields": {
            "name": {"value": "...", "confidence": 0.99, "page": 1, "bounding_box": [...]},
            ...
          }
        }

        UiPath returns various formats depending on the extractor version.
        We handle both the classic and modern API response shapes.
        """
        fields_raw: dict = {}
        overall_confidence = 1.0
        doc_subtype = ""

        # ---- Handle different response shapes ----

        # Shape 1: extractionResult.fieldsValue (modern API)
        if "extractionResult" in raw:
            result = raw["extractionResult"]
            fields_raw = result.get("fieldsValue", result.get("fields", {}))
            overall_confidence = float(raw.get("confidence", 1.0))
            doc_subtype = raw.get("documentTypeId", raw.get("documentType", ""))

        # Shape 2: result.fields (older API)
        elif "result" in raw:
            result = raw["result"]
            fields_raw = result.get("fields", result.get("fieldsValue", {}))
            overall_confidence = float(result.get("confidence", 1.0))
            doc_subtype = raw.get("documentTypeId", "")

        # Shape 3: direct fields (very simple responses)
        elif "fields" in raw:
            fields_raw = raw["fields"]
            overall_confidence = float(raw.get("confidence", 1.0))

        # ---- Determine document type ----
        doc_subtype_lower = doc_subtype.lower().replace(" ", "_").replace("-", "_")
        doc_type = UIPATH_SUBTYPE_MAP.get(doc_subtype_lower)

        if not doc_type:
            # Guess from extractor name
            extractor_type_map = {
                "identity_documents": "PASSPORT",  # generic fallback
                "invoices":           "INSURANCE",
                "receipts":           "GENERIC",
                "contracts":          "GENERIC",
            }
            doc_type = extractor_type_map.get(extractor, "GENERIC")

        # ---- Normalize field names ----
        # UiPath uses camelCase or descriptive names — map to your schema's snake_case
        field_name_map = {
            # Identity documents
            "surname":          "name",
            "given_names":      "name",
            "given_name":       "name",
            "givenName":        "name",
            "lastName":         "name",
            "firstName":        "name",
            "fullName":         "name",
            "full_name":        "name",
            "dateOfBirth":      "dob",
            "date_of_birth":    "dob",
            "birthDate":        "dob",
            "birth_date":       "dob",
            "documentNumber":   "passport_number",
            "document_number":  "passport_number",
            "licenseNumber":    "license_number",
            "license_number":   "license_number",
            "nationality":      "nationality",
            "expiryDate":       "expiry_date",
            "expiry_date":      "expiry_date",
            "dateOfExpiry":     "expiry_date",
            "issueDate":        "issue_date",
            "issue_date":       "issue_date",
            "dateOfIssue":      "issue_date",
            "address":          "address",
            "placeOfBirth":     "place_of_birth",
            "place_of_birth":   "place_of_birth",
            "sex":              "sex",
            "gender":           "sex",
            "issuingCountry":   "nationality",
        }

        # ---- Build normalized fields dict ----
        fields: dict = {}
        for raw_key, raw_val in fields_raw.items():
            # Determine normalized key
            norm_key = field_name_map.get(raw_key, raw_key.lower().replace(" ", "_"))

            # Extract value and confidence from field data
            if isinstance(raw_val, dict):
                value      = raw_val.get("value") or raw_val.get("values", [None])[0]
                confidence = float(raw_val.get("confidence", raw_val.get("ocrConfidence", 1.0)))
                page       = int(raw_val.get("pageIndex", raw_val.get("page", 1)))
                # Bounding box: UiPath uses various formats, we normalize to [x1,y1,x2,y2]
                bbox = self._extract_bbox(raw_val)
            else:
                value      = str(raw_val) if raw_val is not None else None
                confidence = 1.0
                page       = 1
                bbox       = [0, 0, 0, 0]

            if value is None:
                continue

            # Handle "name" collision: if both surname and given_name exist,
            # combine them into a single "name" field
            if norm_key == "name" and "name" in fields:
                existing = fields["name"]["value"] or ""
                new_val  = str(value).strip()
                # Only combine if both are short (individual name parts)
                if len(existing) < 50 and len(new_val) < 50:
                    combined = f"{existing} {new_val}".strip()
                    fields["name"]["value"] = combined
                    continue

            fields[norm_key] = {
                "value":        str(value).strip() if value else "",
                "confidence":   round(min(1.0, max(0.0, confidence)), 3),
                "page":         page,
                "bounding_box": bbox,
            }

        return {
            "document_type": doc_type,
            "confidence":    round(overall_confidence, 3),
            "source_file":   source_file,
            "fields":        fields,
            "_raw_subtype":  doc_subtype,   # keep for debugging
            "_extractor":    extractor,
        }

    def _extract_bbox(self, field_data: dict) -> list[int]:
        """
        Extract a [x1, y1, x2, y2] bounding box from a field's data.
        UiPath returns boxes in various formats.
        """
        # Format 1: {"boundingBox": {"left": 72, "top": 120, "right": 400, "bottom": 140}}
        bbox = field_data.get("boundingBox") or field_data.get("box") or {}
        if isinstance(bbox, dict):
            return [
                int(bbox.get("left", bbox.get("x", 0))),
                int(bbox.get("top",  bbox.get("y", 0))),
                int(bbox.get("right",  bbox.get("x", 0) + bbox.get("width",  0))),
                int(bbox.get("bottom", bbox.get("y", 0) + bbox.get("height", 0))),
            ]

        # Format 2: [x1, y1, x2, y2] already
        if isinstance(bbox, list) and len(bbox) >= 4:
            return [int(v) for v in bbox[:4]]

        return [0, 0, 0, 0]
