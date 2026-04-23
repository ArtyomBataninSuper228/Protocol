from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
import datetime

def generate_key():
    private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    )

    # Сохраняем приватный ключ в файл (PEM формат)
    with open("private_key.pem", "wb") as f:
        f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

    # Извлекаем публичный ключ
    public_key = private_key.public_key()

    # Данные владельца
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, ""),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Telemetry"),
        x509.NameAttribute(NameOID.COMMON_NAME, "my-secure-server.local"),
    ])

    # Сборка сертификата
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365*10)  # Срок 10 лет
    ).sign(private_key, hashes.SHA256())

    # Сохранение сертификата в файл
    with open("certificate.crt", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    generate_key()