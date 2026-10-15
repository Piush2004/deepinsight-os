from cryptography.fernet import Fernet
from api.core.config import settings

class EncryptionService:
    def __init__(self):
        key = settings.ENCRYPTION_KEY
        if not key:
            # Fallback for development if not provided, in production this MUST be set
            key = Fernet.generate_key().decode()
        self.fernet = Fernet(key.encode())

    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self.fernet.decrypt(encrypted_data.encode()).decode()

encryption_service = EncryptionService()
