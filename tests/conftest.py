from __future__ import absolute_import
from __future__ import unicode_literals

import os
import subprocess

import mock
import pytest


@pytest.yield_fixture
def in_tmpdir(tmpdir):
    pwd = os.getcwd()
    os.chdir(tmpdir.strpath)
    try:
        yield
    finally:
        os.chdir(pwd)


@pytest.yield_fixture
def check_call_mock():
    with mock.patch.object(subprocess, 'check_call') as mocked:
        yield mocked
