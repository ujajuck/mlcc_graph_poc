"""Canonical MLCC spec schema.

Re-exports Pydantic models from `spec_schema` so callers can write::

    from schema import Product, Spec, Exception_, TestCondition, Source
"""
from schema.spec_schema import (
    Exception_,
    Product,
    ProductFamily,
    Source,
    Spec,
    TemperatureCharacteristic,
    TestCondition,
)

__all__ = [
    "Exception_",
    "Product",
    "ProductFamily",
    "Source",
    "Spec",
    "TemperatureCharacteristic",
    "TestCondition",
]
