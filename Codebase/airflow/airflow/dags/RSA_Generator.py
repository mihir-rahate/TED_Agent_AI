from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os

def generate_rsa_key_pair():
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Get private key in PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Get public key in PEM format
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Save private key
    with open('snowflake_key.pem', 'wb') as f:
        f.write(private_pem)
    
    # Save public key
    with open('snowflake_key.pub', 'wb') as f:
        f.write(public_pem)
    
    print("RSA key pair generated successfully!")
    print(f"Private key saved to: snowflake_key.pem")
    print(f"Public key saved to: snowflake_key.pub")
    
    # Display public key for Snowflake
    public_key_str = public_pem.decode('utf-8')
    print("\nPublic key for Snowflake (copy everything including ---BEGIN and ---END):")
    print(public_key_str)

# Run the function
generate_rsa_key_pair()