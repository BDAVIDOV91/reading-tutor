"""Input device class and hash (ADR 0001): the raw browser label is never returned or stored.

Labels are invented. Bluetooth labels often carry a person's name, which is why only class + hash are kept.
"""

from __future__ import annotations

import pytest

from reading_tutor.audio import device_class, device_hash

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Иван's AirPods", "bluetooth"),
        ("Galaxy Buds2 Pro (Bluetooth)", "bluetooth"),
        ("Headset (WH-1000XM4 Hands-Free AG Audio)", "bluetooth"),
        ("bluez_input.AA_BB_CC_DD_EE_FF.0", "bluetooth"),
        ("Blue Yeti USB Microphone (046d:0ab7)", "usb"),
        ("USB PnP Sound Device Analog Mono", "usb"),
        ("Headset Microphone (Jabra EVOLVE 20)", "headset"),
        ("Built-in Audio Analog Stereo", "builtin"),
        ("Internal Microphone", "builtin"),
        ("MacBook Air Microphone", "builtin"),
        ("Microphone Array (Realtek(R) Audio)", "builtin"),
        ("Default", "builtin"),
        ("Fake Default Audio Input", "builtin"),
        ("", "unknown"),
        ("Something Else 3000", "unknown"),
    ],
)
def test_device_class(label: str, expected: str):
    assert device_class(label) == expected


def test_device_class_never_returns_the_label():
    label = "Иван's AirPods"
    assert "Иван" not in device_class(label)
    assert "Иван" not in device_hash(label)


def test_device_hash_is_short_stable_and_label_specific():
    h = device_hash("Иван's AirPods")
    assert h == device_hash("Иван's AirPods")
    assert h != device_hash("Мария's AirPods")
    assert len(h) == 12 and int(h, 16) >= 0


def test_empty_label_has_no_hash():
    assert device_hash("") is None


def test_device_hash_depends_on_the_install_secret():
    """Privacy review 2026-11-18, finding 5: an unsalted hash of '<Name>'s AirPods' can be reversed by guessing."""
    import hashlib

    label = "Иван's AirPods"
    a, b = device_hash(label, secret=b"a" * 32), device_hash(label, secret=b"b" * 32)
    assert a != b
    assert a != hashlib.sha256(label.encode()).hexdigest()[:12]
