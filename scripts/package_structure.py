"""Read cmix-neif's compressor footer and construct its actual decoder prefix."""
import hashlib
import struct

MAGIC = b"B5JPAYLOAD_V1__"


def inspect(data):
    if len(data) < 80 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF compressor package")
    hints, order, payload, weights = struct.unpack("<4i", data[-16:])
    if min(hints, order, weights) <= 0 or payload != 0:
        raise ValueError("requires the compressor footer, not a data archive")
    program_bytes = len(data) - 16 - hints - order - weights
    if program_bytes < 64:
        raise ValueError("footer blocks extend beyond the package")
    position = data.find(MAGIC, 0, min(program_bytes, 1 << 20))
    if position < 0 or position + 64 > min(program_bytes, 1 << 20):
        raise ValueError("packed program header missing")
    fields = struct.unpack_from("<6Q", data, position + 16)
    offset, compressed, decoded, image, split, decoder_compressed = fields
    if (offset < position + 64 or offset + compressed != program_bytes or decoded != image
            or not 0 < split < image or not 0 < decoder_compressed <= compressed):
        raise ValueError("invalid packed program boundaries")
    decoder = bytearray(data[:offset + decoder_compressed])
    struct.pack_into("<Q", decoder, position + 24, decoder_compressed)
    struct.pack_into("<Q", decoder, position + 32, split)
    blocks, start = {}, program_bytes
    for name, length in (("hints", hints), ("order", order), ("weights", weights)):
        block = data[start:start + length]
        blocks[name] = {"bytes": length, "sha256": hashlib.sha256(block).hexdigest()}
        if name == "weights" and block[:8] != b"FX2TFWC4":
            raise ValueError("weight block is not the expected container format")
        start += length
    return {"compressor_bytes": len(data), "compressor_sha256": hashlib.sha256(data).hexdigest(),
            "packed_program_bytes": program_bytes, "decoder_prefix_bytes": len(decoder),
            "decoder_prefix_sha256": hashlib.sha256(decoder).hexdigest(), "blocks": blocks,
            "component_bytes_excluding_dictionary_payload_footer_args": len(data) + len(decoder) + weights}, bytes(decoder)
