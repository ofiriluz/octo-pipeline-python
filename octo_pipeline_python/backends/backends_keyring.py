import base64
import hashlib
import json
import os
import socket
import sys
from datetime import datetime
from platform import uname
from typing import Dict, Final, Optional

from dateutil import parser

BLOCK_SIZE: Final[int] = 32


class BasicKeyring:
    def __init__(self, base_keyring_dir: str) -> None:
        self.__basic_folder_path = os.path.join(
            base_keyring_dir, ".cache", ".keyring")
        if not os.path.exists(self.__basic_folder_path):
            os.makedirs(self.__basic_folder_path)
        self.__keyring_file_path = os.path.join(
            self.__basic_folder_path, "keyring")
        self.__mac_file_path = os.path.join(self.__basic_folder_path, "mac")

    @staticmethod
    def __encrypt(secret: bytes, data: str) -> Dict:
        # Create a cipher with the secret and default nonce
        from Crypto.Cipher import AES
        cipher = AES.new(secret, AES.MODE_GCM)
        # Encrypt the data and generate a tag for later validation of the encryption
        ciphertext, tag = cipher.encrypt_and_digest(data.encode())
        # Create the json encrypted packet (all values are also base64 encoded)
        json_k = ['nonce', 'ciphertext', 'tag']
        json_v = [base64.b64encode(x).decode('utf-8')
                  for x in [cipher.nonce, ciphertext, tag]]
        return dict(zip(json_k, json_v))

    @staticmethod
    def __decrypt(secret: bytes, data: Dict) -> bytes:
        # Prepare the base 64 decoded json
        jv = {k: base64.b64decode(data[k]) for k in data.keys()}
        # Perform the decryption and verification
        from Crypto.Cipher import AES
        cipher = AES.new(secret, AES.MODE_GCM, nonce=jv['nonce'])
        return cipher.decrypt_and_verify(jv['ciphertext'], jv['tag'])

    def __get_current_mac(self) -> str:
        if not os.path.exists(self.__mac_file_path):
            raise RuntimeError("Invalid keyring path")
        with open(self.__mac_file_path, 'r') as f:
            return f.read()

    def __validate_mac_and_get_data(self) -> Optional[str]:
        mac = self.__get_current_mac()
        with open(self.__keyring_file_path, 'r') as f:
            data = f.read()
            data_mac = hashlib.sha256(data.encode()).hexdigest()
            if data_mac == mac:
                return data
        return None

    def __update_mac(self) -> None:
        if not os.path.exists(self.__keyring_file_path):
            raise RuntimeError("Invalid keyring path")
        with open(self.__keyring_file_path, 'r') as f:
            data = f.read()
            data_mac = hashlib.sha256(data.encode()).hexdigest()
            with open(self.__mac_file_path, 'w') as macf:
                macf.write(data_mac)

    def set_password(self, service_name: str, secret_name: str, secret: str) -> None:
        from Crypto.Util.Padding import pad
        key = pad(socket.gethostname().encode(), BLOCK_SIZE)
        existing_keyring = {}
        if os.path.exists(self.__keyring_file_path):
            data = self.__validate_mac_and_get_data()
            if not data:
                raise RuntimeError("Keyring validation failed")
            existing_keyring = json.loads(data)
        if service_name not in existing_keyring:
            existing_keyring[service_name] = {}
        existing_keyring[service_name][secret_name] = self.__encrypt(
            key, secret)
        with open(self.__keyring_file_path, 'w') as f:
            json.dump(existing_keyring, f)
        self.__update_mac()

    def get_password(self, service_name: str, secret_name: str) -> Optional[str]:
        from Crypto.Util.Padding import pad
        key = pad(socket.gethostname().encode(), BLOCK_SIZE)
        if not os.path.exists(self.__keyring_file_path):
            return None
        data = self.__validate_mac_and_get_data()
        if not data:
            raise RuntimeError("Keyring validation failed")
        existing_keyring = json.loads(data)
        try:
            return self.__decrypt(key, existing_keyring[service_name][secret_name]).decode()
        except (KeyError, ValueError):
            return None

    def delete_password(self, service_name: str, secret_name: str) -> None:
        if not os.path.exists(self.__keyring_file_path):
            return
        data = self.__validate_mac_and_get_data()
        if not data:
            raise RuntimeError("Keyring validation failed")
        existing_keyring = json.loads(data)
        if service_name not in existing_keyring or secret_name not in existing_keyring[service_name]:
            return
        del existing_keyring[service_name][secret_name]
        with open(self.__keyring_file_path, 'w') as f:
            json.dump(existing_keyring, f)
        self.__update_mac()


class BackendsKeyring:
    def __init__(self, keyring_path: str):
        self.__keyring_path = keyring_path

    @staticmethod
    def __is_docker():
        path = '/proc/self/cgroup'
        return (
            os.path.exists('/.dockerenv')
            or os.path.isfile(path) and any('docker' in line for line in open(path))
        )

    def __get_keyring(self):
        try:
            import keyring
            from keyring.backends import SecretService, macOS

            # Docker or WSL or explicit usage of basic keyring
            if BackendsKeyring.__is_docker() \
                    or 'Microsoft' in uname().release \
                    or sys.platform.__contains__("sunos") \
                    or "PIPELINE_BASIC_KEYRING" in os.environ:
                return BasicKeyring(self.__keyring_path)
            if sys.platform == "win32":
                from keyrings.cryptfile.cryptfile import CryptFileKeyring
                kr = CryptFileKeyring()
                kr.keyring_key = socket.gethostname()
                return kr
            elif sys.platform == "darwin":
                return macOS.Keyring()
            else:
                return SecretService.Keyring()
        except:
            return BasicKeyring(self.__keyring_path)

    def save_secret(self, backend: str, secret: Dict,
                    expiration_time: datetime, tag: Optional[str] = None) -> None:
        if expiration_time:
            secret["expiration_time"] = str(expiration_time)
        kr = self.__get_keyring()
        kr.set_password(backend,
                        tag or f"{backend}-secret", json.dumps(secret))

    def load_secret(self, backend: str, tag: Optional[str] = None) -> Optional[Dict]:
        kr = self.__get_keyring()
        secret_val = kr.get_password(backend, tag or f"{backend}-secret")
        if not secret_val:
            return None
        secret = json.loads(secret_val)
        if 'expiration_time' in secret:
            expiration_time = parser.parse(secret["expiration_time"])
            if expiration_time.replace(tzinfo=None) < datetime.now():
                kr.delete_password(backend, tag or f"{backend}-secret")
                return None
        return secret

    def delete_secret(self, backend: str, tag: Optional[str] = None):
        kr = self.__get_keyring()
        kr.delete_password(backend, tag or f"{backend}-secret")
