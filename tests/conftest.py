from __future__ import annotations

import os
import subprocess
from unittest import mock

import pytest


@pytest.fixture
def in_tmpdir(tmpdir):
    pwd = os.getcwd()
    os.chdir(tmpdir.strpath)
    try:
        yield
    finally:
        os.chdir(pwd)


@pytest.fixture
def check_call_mock():
    with mock.patch.object(subprocess, 'check_call') as mocked:
        yield mocked
