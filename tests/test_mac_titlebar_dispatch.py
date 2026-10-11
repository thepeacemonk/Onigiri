"""Verify the native dispatch ABI without loading AppKit or touching a window."""
import ctypes
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class MacTitlebarDispatchTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'integrations/mac_titlebar.py'
        spec = importlib.util.spec_from_file_location('titlebar_dispatch_fixture', source)
        self.module = importlib.util.module_from_spec(spec)
        aqt = types.ModuleType('aqt')
        aqt.mw = None
        with patch.dict(sys.modules, {'aqt': aqt}):
            spec.loader.exec_module(self.module)
        self.runtime = types.SimpleNamespace(
            objc_msgSend=ctypes.c_void_p(100),
            objc_msgSend_stret=ctypes.c_void_p(200),
            sel_registerName=lambda name: 123,
        )

    def dispatch(self, architecture, restype):
        signatures, calls = [], []

        def prototype(result, *arguments):
            signatures.append((result, arguments))

            def bind(address):
                def invoke(*args):
                    calls.append((address, args))
                    return 'result'
                return invoke
            return bind

        with patch.object(self.module, '_runtime', return_value=self.runtime), \
                patch('platform.machine', return_value=architecture), \
                patch.object(ctypes, 'CFUNCTYPE', side_effect=prototype):
            self.assertEqual(self.module._send(321, 'frame', restype=restype), 'result')
        self.assertEqual(signatures, [(restype, (ctypes.c_void_p, ctypes.c_void_p))])
        self.assertEqual(calls[0][1], (321, 123))
        return calls[0][0]

    def test_intel_rect_uses_structure_return_dispatch(self):
        self.assertEqual(self.dispatch('x86_64', self.module._NSRect), 200)

    def test_apple_silicon_rect_uses_regular_dispatch(self):
        del self.runtime.objc_msgSend_stret  # This symbol does not exist on arm64.
        self.assertEqual(self.dispatch('arm64', self.module._NSRect), 100)

    def test_scalar_and_void_returns_keep_regular_dispatch_on_both_architectures(self):
        for architecture in ('x86_64', 'arm64'):
            for result in (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_bool, None):
                with self.subTest(architecture=architecture, result=result):
                    self.assertEqual(self.dispatch(architecture, result), 100)

    def test_unavailable_runtime_does_not_dispatch(self):
        with patch.object(self.module, '_runtime', return_value=None):
            self.assertIsNone(self.module._send(321, 'frame', restype=self.module._NSRect))
