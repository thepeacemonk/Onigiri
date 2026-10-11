"""Exercise the haptic FFI boundary without importing Anki or loading AppKit."""

import ast
import ctypes
import ctypes.util
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class MacHapticFeedbackTests(unittest.TestCase):
    def setUp(self):
        source = (ROOT / "settings_web" / "dialog.py").read_text()
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_trigger_mac_haptic_native"
        )
        self.platform = SimpleNamespace(is_supported=lambda: True)
        namespace = {"mac_titlebar": self.platform}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "dialog.py", "exec"), namespace)
        self.trigger = namespace[function.name]

        # Invalid if dereferenced, but safe to pass through these native C
        # callbacks.  Their low 32 bits resemble the reported fault address.
        self.class_pointer = 0x123405514C40
        self.performer_pointer = 0x567805514C40
        self.default_selector = 0x123400001001
        self.feedback_selector = 0x123400001002
        self.object_calls = []
        self.feedback_calls = []
        self.prototypes = []
        self.function_type = ctypes.CFUNCTYPE

        def lookup_selector(name):
            return {
                b"defaultPerformer": self.default_selector,
                b"performFeedbackPattern:performanceTime:": self.feedback_selector,
            }[name]

        def get_performer(receiver, selector):
            self.object_calls.append((receiver, selector))
            return self.performer_pointer

        def perform_feedback(receiver, selector, pattern, performance_time):
            self.feedback_calls.append((receiver, selector, pattern, performance_time))

        self.getter = self.function_type(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(get_performer)
        self.feedback = self.function_type(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_ulong
        )(perform_feedback)
        self.objc = SimpleNamespace(
            objc_getClass=self.function_type(ctypes.c_void_p, ctypes.c_char_p)(
                lambda name: self.class_pointer
            ),
            sel_registerName=self.function_type(ctypes.c_void_p, ctypes.c_char_p)(lookup_selector),
            objc_msgSend=self.getter,
        )

    def call(self, pattern=2, load_error=None):
        def prototype(restype, *argtypes):
            self.prototypes.append((restype, argtypes))
            signature = self.function_type(restype, *argtypes)

            def bind(address):
                self.assertEqual(address, ctypes.cast(self.objc.objc_msgSend, ctypes.c_void_p).value)
                native = self.feedback if restype is None else self.getter
                # Call a real C function pointer through the signature the
                # helper chose, so narrowing pointer arguments is observable.
                return signature(ctypes.cast(native, ctypes.c_void_p).value)

            return bind

        with ExitStack() as stack:
            stack.enter_context(patch("ctypes.util.find_library", side_effect=lambda name: name))
            loader = stack.enter_context(patch(
                "ctypes.cdll.LoadLibrary",
                side_effect=load_error or (lambda name: self.objc if name == "objc" else object()),
            ))
            stack.enter_context(patch("ctypes.CFUNCTYPE", side_effect=prototype))
            self.trigger(pattern)
        return loader

    def test_native_calls_preserve_64_bit_pointers_and_method_signatures(self):
        for pattern in (0, 1, 2):
            self.call(pattern)
        self.assertEqual(self.object_calls, [(self.class_pointer, self.default_selector)] * 3)
        self.assertEqual(self.feedback_calls, [
            (self.performer_pointer, self.feedback_selector, pattern, 0)
            for pattern in (0, 1, 2)
        ])
        self.assertEqual(self.prototypes, [
            (ctypes.c_void_p, (ctypes.c_void_p, ctypes.c_void_p)),
            (None, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_ulong)),
        ] * 3)
        self.assertEqual(self.objc.objc_getClass.argtypes, [ctypes.c_char_p])
        self.assertEqual(self.objc.sel_registerName.argtypes, [ctypes.c_char_p])

    def test_other_platforms_do_not_load_native_libraries(self):
        self.platform.is_supported = lambda: False
        self.call().assert_not_called()

    def test_unsupported_patterns_do_not_reach_appkit(self):
        self.call(99).assert_not_called()

    def test_missing_class_does_not_send_messages(self):
        self.class_pointer = 0
        self.call()
        self.assertEqual(self.object_calls, [])
        self.assertEqual(self.feedback_calls, [])

    def test_missing_performer_does_not_request_feedback(self):
        self.performer_pointer = 0
        self.call()
        self.assertEqual(self.feedback_calls, [])

    def test_unavailable_runtime_does_not_interrupt_settings(self):
        self.call(load_error=OSError("runtime unavailable"))
        self.assertEqual(self.feedback_calls, [])


if __name__ == "__main__":
    unittest.main()
