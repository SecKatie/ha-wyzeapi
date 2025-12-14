import binascii
from typing import Dict

from Crypto.Cipher import AES


def decrypt_ecb(key: str, data: bytes) -> bytes:
    key_bytes = key.encode()
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    decrypted_data = cipher.decrypt(data)
    return decrypted_data


def encrypt_ecb(key: str, data: bytes) -> bytes:
    key_bytes = key.encode()
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    encrypted_data = cipher.encrypt(data)
    return encrypted_data


def pack_l1(flags: int, seq_no: int, data: bytes):
    data_crc = crc(data)
    result = b"\xab"
    result += flags.to_bytes(1)
    result += len(data).to_bytes(2)
    result += data_crc.to_bytes(2)
    result += seq_no.to_bytes(2)
    result += data
    return result


def parse_l1(data: bytes):
    if data[0] != 0xAB:
        raise ValueError("Unexpected data")
    flags = data[1]
    length = int.from_bytes(data[2:4])
    data_crc = int.from_bytes(data[4:6])
    seq_no = int.from_bytes(data[6:8])
    l2_content = data[8:]
    if len(l2_content) > length:
        l2_content = l2_content[:length]
    if len(l2_content) == length and crc(l2_content) != data_crc:
        raise ValueError(f"CRC Checksum failed! {data_crc} != {crc(l2_content)}")
    return l2_content, flags, seq_no, length - len(l2_content)


def pack_l2_dict(cmd: int, flags: int, content: Dict[int, bytes]):
    result = cmd.to_bytes(1)
    result += flags.to_bytes(1)
    for k, v in content.items():
        result += k.to_bytes(1)
        result += len(v).to_bytes(2)
        result += v
    return result


def parse_l2_dict(data: bytes):
    result_dict: Dict[int, bytes] = {}
    cmd = data[0]
    flags = data[1]
    cur = 2
    while cur < len(data):
        key = data[cur]
        length = int.from_bytes(data[cur + 1 : cur + 3])
        value = data[cur + 3 : cur + 3 + length]
        result_dict[key] = value
        cur += 3 + length
    return cmd, flags, result_dict


def pack_l2_lock_unlock(ble_id: int, ble_token: str, challenge: bytes, command):
    if command == "unlock":
        magic_bytes = binascii.unhexlify("01000000000000000000006C6F6F636B")
    elif command == "lock":
        magic_bytes = binascii.unhexlify("02000000000000000000006C6F6F636B")
    else:
        raise ValueError(f"Only accept `lock` or `unlock`, but got `{command}`")
    encrypted_challenge = encrypt_ecb(ble_token[16:], challenge)
    encrypted_challenge = b"".join(
        (x ^ y).to_bytes(1) for x, y in zip(encrypted_challenge, magic_bytes)
    )
    result = (0x0400050002).to_bytes(5)
    result += ble_id.to_bytes(2)
    result += (0x040010).to_bytes(3)
    result += encrypted_challenge
    result += (0xAD000100F4000101F7000101).to_bytes(12)
    return result


def crc(data):
    magic = (
        "0000c0c1c1810140c30103c00280c241c60106c00780c7410500c5c1c4810440"
        "cc010cc00d80cd410f00cfc1ce810e400a00cac1cb810b40c90109c00880c841"
        "d80118c01980d9411b00dbc1da811a401e00dec1df811f40dd011dc01c80dc41"
        "1400d4c1d5811540d70117c01680d641d20112c01380d3411100d1c1d0811040"
        "f00130c03180f1413300f3c1f28132403600f6c1f7813740f50135c03480f441"
        "3c00fcc1fd813d40ff013fc03e80fe41fa013ac03b80fb413900f9c1f8813840"
        "2800e8c1e9812940eb012bc02a80ea41ee012ec02f80ef412d00edc1ec812c40"
        "e40124c02580e5412700e7c1e68126402200e2c1e3812340e10121c02080e041"
        "a00160c06180a1416300a3c1a28162406600a6c1a7816740a50165c06480a441"
        "6c00acc1ad816d40af016fc06e80ae41aa016ac06b80ab416900a9c1a8816840"
        "7800b8c1b9817940bb017bc07a80ba41be017ec07f80bf417d00bdc1bc817c40"
        "b40174c07580b5417700b7c1b68176407200b2c1b3817340b10171c07080b041"
        "500090c191815140930153c052809241960156c057809741550095c194815440"
        "9c015cc05d809d415f009fc19e815e405a009ac19b815b40990159c058809841"
        "880148c0498089414b008bc18a814a404e008ec18f814f408d014dc04c808c41"
        "440084c185814540870147c046808641820142c043808341410081c180814040"
    )
    magic = [
        int.from_bytes(binascii.unhexlify(magic[x : x + 4]))
        for x in range(0, len(magic), 4)
    ]
    result = 0
    for b in data:
        result = magic[(result ^ (b & 255)) & 255] ^ (result >> 8)
    return 65535 & result
