"""Private release signing key never enters client packages or website files."""
import base64,json
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import rsa,padding
ROOT=Path(__file__).resolve().parents[2]
KEY=ROOT/'data/windows-client/private/update-signing.pem'
def key():
    KEY.parent.mkdir(parents=True,exist_ok=True)
    if not KEY.exists():
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        with KEY.open('xb') as stream:stream.write(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return serialization.load_pem_private_key(KEY.read_bytes(),password=None)
def prepare_key():
    numbers=key().public_key().public_numbers()
    encode=lambda v:base64.b64encode(v.to_bytes((v.bit_length()+7)//8,'big')).decode()
    xml='<RSAKeyValue><Modulus>'+encode(numbers.n)+'</Modulus><Exponent>'+encode(numbers.e)+'</Exponent></RSAKeyValue>'
    (Path(__file__).parent/'UpdateKey.cs').write_text('namespace MhpClient { internal static class UpdateKey { internal const string PublicXml="'+xml+'"; } }',encoding='utf-8')
def sign(value):
    payload=json.dumps(value,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()
    signature=key().sign(payload,padding.PKCS1v15(),hashes.SHA256())
    return {'payload':base64.b64encode(payload).decode(),'signature':base64.b64encode(signature).decode()}
