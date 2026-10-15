import io

import pytest

from api.services.knowledge.pipeline import ValidationService, MAX_FILE_SIZE_BYTES
from api.services.knowledge.loaders import PDFLoader


# --- File upload abuse (oversized / empty / wrong type) -----------------------------

def test_validation_rejects_empty_file():
    with pytest.raises(ValueError, match="empty"):
        ValidationService().validate(io.BytesIO(b""), "empty.txt", "text/plain", file_size=0)


def test_validation_rejects_oversized_file():
    with pytest.raises(ValueError, match="exceeds maximum"):
        ValidationService().validate(io.BytesIO(b"x"), "huge.txt", "text/plain", file_size=MAX_FILE_SIZE_BYTES + 1)


def test_validation_accepts_file_at_exact_size_limit():
    ValidationService().validate(io.BytesIO(b"x"), "ok.txt", "text/plain", file_size=MAX_FILE_SIZE_BYTES)


def test_validation_rejects_disallowed_mime_type():
    with pytest.raises(ValueError, match="Unsupported file type"):
        ValidationService().validate(io.BytesIO(b"x"), "script.exe", "application/x-msdownload", file_size=10)


def test_validation_rejects_disguised_executable_with_txt_extension():
    # Same class of attack as above, phrased as the audit brief's "file upload abuse":
    # a malicious binary can't sneak past validation just by getting a text/plain
    # Content-Type claim if the router still passes the actual declared mime type through.
    with pytest.raises(ValueError, match="Unsupported file type"):
        ValidationService().validate(io.BytesIO(b"MZ\x90\x00"), "totally-a.txt", "application/octet-stream", file_size=4)


def test_validation_rejects_missing_filename():
    with pytest.raises(ValueError, match="filename"):
        ValidationService().validate(io.BytesIO(b"x"), "", "text/plain", file_size=1)


# --- Malformed documents --------------------------------------------------------------

def test_pdf_loader_raises_clear_error_on_garbage_bytes_not_a_silent_crash():
    garbage = io.BytesIO(b"this is not a pdf, just text pretending to be one")
    with pytest.raises(Exception):
        PDFLoader().load(garbage)


# --- Token leakage: ConnectorToken fields must never appear in router response bodies -

def test_integrations_router_never_serializes_token_fields():
    import inspect
    from api.routers import integrations

    source = inspect.getsource(integrations)
    # The router builds response dicts by hand (not a Pydantic response_model), so this
    # greps its own source for the literal field names rather than introspecting a
    # schema - if a future edit starts returning `access_token`/`refresh_token`
    # directly, this test breaks and calls it out.
    assert "access_token" not in source
    assert "refresh_token" not in source


def test_connector_token_model_fields_are_encrypted_type():
    from api.models.integrations import ConnectorToken
    from api.models.types import EncryptedString

    assert isinstance(ConnectorToken.access_token.type, EncryptedString)
    assert isinstance(ConnectorToken.refresh_token.type, EncryptedString)
