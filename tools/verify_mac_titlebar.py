"""Verify native rectangle dispatch without opening Anki or creating a window.

Run with Anki's Python environment on macOS. The compiler comparison requires
Xcode command-line tools; its artifacts stay in a temporary directory.
"""
import ctypes
import importlib.util
import platform
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.modules['aqt'] = types.SimpleNamespace(mw=None)
spec = importlib.util.spec_from_file_location('titlebar_native_probe', ROOT / 'integrations/mac_titlebar.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
runtime = bridge._runtime()
runtime.objc_getClass.restype = ctypes.c_void_p
runtime.objc_getClass.argtypes = [ctypes.c_char_p]
pool = bridge._send(runtime.objc_getClass(b'NSAutoreleasePool'), 'alloc')
pool = bridge._send(pool, 'init')
try:
    rectangle = bridge._NSRect(bridge._NSPoint(1, 2), bridge._NSSize(3, 4))
    value = bridge._send(runtime.objc_getClass(b'NSValue'), 'valueWithRect:', rectangle,
                         argtypes=[bridge._NSRect])
    frame = bridge._send(value, 'rectValue', restype=bridge._NSRect)
    assert (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height) == (1, 2, 3, 4)
    print(f'PASS: actual {platform.machine()} Objective-C rectangle round trip; no window created.')
finally:
    bridge._send(pool, 'drain', restype=None)

with tempfile.TemporaryDirectory(prefix='onigiri-objc-abi-') as tmp:
    source = Path(tmp) / 'probe.m'
    source.write_text('#import <Foundation/Foundation.h>\nNSRect probe(NSValue *value) { return [value rectValue]; }\n')
    for architecture in ('x86_64', 'arm64'):
        assembly = Path(tmp) / (architecture + '.s')
        subprocess.run(['xcrun', 'clang', '-arch', architecture, '-S', str(source), '-o', str(assembly)], check=True)
        generated = assembly.read_text()
        if architecture == 'x86_64':
            assert 'callq\t_objc_msgSend_stret' in generated
        else:
            assert '_objc_msgSend$rectValue' in generated and 'objc_msgSend_stret' not in generated
        print(f'PASS: Apple compiler confirms the rectangle return convention for {architecture}.')
print('Compiler checks for the other architecture do not constitute a native execution test on that hardware.')
