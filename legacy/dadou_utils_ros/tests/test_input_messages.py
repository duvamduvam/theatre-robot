"""Tests d'InputMessagesList (singleton de file de messages du contrôleur)."""

import pytest

from dadou_utils_ros.com.input_messages_list import InputMessagesList


@pytest.fixture
def messages():
    instance = InputMessagesList()
    instance.pop_msg()  # vide l'état partagé du singleton entre les tests
    return instance


def test_empty_by_default(messages):
    assert messages.has_msg() is False
    assert messages.pop_msg() == {}


def test_add_then_pop(messages):
    messages.add_msg({"neck": 0.5})
    assert messages.has_msg() is True
    assert messages.pop_msg() == {"neck": 0.5}
    assert messages.has_msg() is False


def test_messages_merge_by_key(messages):
    messages.add_msg({"neck": 0.5})
    messages.add_msg({"neck": 0.8, "audio": "hello.mp3"})
    assert messages.pop_msg() == {"neck": 0.8, "audio": "hello.mp3"}


def test_singleton_shares_state(messages):
    InputMessagesList().add_msg({"key": "a"})
    assert messages.has_msg() is True
    assert InputMessagesList() is messages
