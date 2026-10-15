from sqlalchemy.types import TypeDecorator, Text
from api.utils.encryption import encryption_service


class EncryptedString(TypeDecorator):
    """Transparently encrypts/decrypts a string column at rest using EncryptionService.
    Shared across any model that stores a secret (OAuth tokens, API keys, etc.) -
    do not redefine this per-model."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encryption_service.encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return encryption_service.decrypt(value)
        return value
