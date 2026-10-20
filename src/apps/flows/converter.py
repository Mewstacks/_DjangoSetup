"""The data converter every client and worker uses: pydantic types, optionally sealed."""

from __future__ import annotations

import dataclasses

from django.conf import settings
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.converter import DataConverter

from apps.flows.codec import EncryptionCodec


def build_data_converter() -> DataConverter:
    if settings.TEMPORAL_PAYLOAD_ENCRYPTION:
        return dataclasses.replace(pydantic_data_converter, payload_codec=EncryptionCodec())
    return pydantic_data_converter
