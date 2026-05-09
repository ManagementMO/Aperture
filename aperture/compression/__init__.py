"""Schema-aware output compression."""

from aperture.compression.compressor import compress_tool_output
from aperture.compression.profile_loader import CompressionProfile, load_compression_profile

__all__ = ["CompressionProfile", "compress_tool_output", "load_compression_profile"]

