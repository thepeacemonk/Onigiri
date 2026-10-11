"""Verify backup/sync with actual Anki and warning rendering with offscreen Qt.

Run with Anki's Python environment. All collection/file writes are confined to
TemporaryDirectory; screenshots are written to /tmp. No Anki window is opened.
"""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import copy, importlib.util, json, sys, tempfile, types, zipfile
from pathlib import Path
from unittest.mock import patch
from anki.collection import Collection
from PyQt6 import QtWidgets, QtGui, QtCore
ROOT = Path(__file__).resolve().parents[1]
pkg=types.ModuleType('warning_audit');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
core=types.ModuleType('warning_audit.core');core.__path__=[str(ROOT/'core')];sys.modules[core.__name__]=core
cfg=types.ModuleType('warning_audit.core.config');cfg.get_config_readonly=lambda: {};sys.modules[cfg.__name__]=cfg
core.config=cfg
host=types.ModuleType('aqt');sys.modules['aqt']=host

def load(name, path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

with tempfile.TemporaryDirectory(prefix='onigiri-real-anki-') as tmp:
 collection=Collection(str(Path(tmp)/'collection.anki2'))
 try:
  values={'onigiri_hashi_notes':[{'id':'note-1','body_md':'Keep my notes'}], 'modern_menu_statsTitle':'Saved title', 'unrelated_setting':{'keep':True}}
  for k,v in values.items():collection.set_config(k,v)
  host.mw=types.SimpleNamespace(col=collection,pm=types.SimpleNamespace(name='Audit',base=tmp))
  storage=load('warning_audit.core.safe_storage',ROOT/'core/safe_storage.py');core.safe_storage=storage
  storage.__file__=str(Path(tmp)/'addons21/onigiri/core/safe_storage.py')
  Path(storage.user_files_dir(),'settings_Audit.json').write_text('{"userName":"Learner"}')
  try:dict(collection.conf)
  except TypeError as exc:assert str(exc)=='bad argument type for built-in operation';print('Reproduced the exact reported error with installed Anki ConfigManager.')
  else:raise AssertionError('Expected old dict conversion to fail')
  before=collection.all_config()
  archive=storage.backup_before_upgrade({'legacy':True});assert archive and Path(archive).is_file()
  backup=next(Path(storage.external_backup_dir()).glob('before_progress_upgrade_v2_*.json'))
  assert json.loads(backup.read_text())['collection_config']==before
  assert collection.all_config()==before
  assert storage.take_notices()==[]
  sync=load('warning_audit.core.sync',ROOT/'core/sync.py')
  manager=sync.SyncManager();manager._user_files_dir=storage.user_files_dir();manager._state_file=str(Path(storage.user_files_dir())/'sync_state.json')
  assert manager.pack_user_files(force=True)
  with zipfile.ZipFile(manager.get_sync_file_path()) as z:manifest=json.loads(z.read(sync.SYNC_MANIFEST))
  saved={k:v for group in manifest['collection_config'].values() for k,v in group.items()}
  assert saved['onigiri_hashi_notes']==values['onigiri_hashi_notes'] and saved['modern_menu_statsTitle']==values['modern_menu_statsTitle']
  assert 'unrelated_setting' not in saved
  print('PASS: actual Anki collection backup is complete and unchanged; sync retains Onigiri collection keys.')
 finally:collection.close()

host.mw=None
qt=types.ModuleType('aqt.qt')
for module in (QtWidgets, QtGui, QtCore):
 for name in dir(module):
  if not name.startswith('_'):setattr(qt,name,getattr(module,name))
sys.modules['aqt.qt']=qt
theme=types.ModuleType('aqt.theme');theme.theme_manager=types.SimpleNamespace(night_mode=False);sys.modules['aqt.theme']=theme
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
notifications=load('warning_audit.ui_kit.onigiri_notifications',ROOT/'ui_kit/onigiri_notifications.py')
for dark in (False,True):
 theme.theme_manager.night_mode=dark
 dialog=notifications.OnigiriInfoDialog('Onigiri could not back up your collection settings. Your saved settings were not changed.\n\nDetails: bad argument type for built-in operation',title='Backup and recovery')
 dialog.show();app.processEvents()
 assert dialog.windowTitle()=='Onigiri · Backup and recovery'
 icon=dialog.findChild(QtWidgets.QLabel,'onigiriInfoIcon');assert not icon.pixmap().isNull()
 assert dialog.findChild(QtWidgets.QLabel,'onigiriInfoTitle').text().startswith('Onigiri')
 path=f'/tmp/onigiri-warning-preview-{ "dark" if dark else "light"}.png';assert dialog.grab().save(path)
 dialog.findChild(QtWidgets.QPushButton,'onigiriInfoOk').click();assert dialog.result()==QtWidgets.QDialog.DialogCode.Accepted
 long=notifications.OnigiriInfoDialog('\n\n'.join(['Arquivo / folder: ' + 'very-long-name-'*20]*12),title='Aviso')
 long.show();app.processEvents()
 scroll=long.findChild(QtWidgets.QScrollArea);assert scroll.verticalScrollBar().maximum()>0
 assert long.height()<=app.primaryScreen().availableGeometry().height()*.8
 long.reject()
 box=QtWidgets.QMessageBox();notifications.brand_message_box(box,'Aviso');assert box.text()=='Onigiri · Aviso' and not box.iconPixmap().isNull()
 print(f'PASS: native {"dark" if dark else "light"} logo, title, OK, scroll, confirmation branding; screenshot {path}')
with patch.object(notifications,'_native_show_info') as show:
 notifications.notify_warning('Saved data needs attention', title='Warning', gamification=True)
 show.assert_called_once_with('Saved data needs attention',title='Warning',parent=None)
print('PASS: warnings are persistent and bypass game-notification silent mode.')

seen=[]
with patch.object(notifications, 'OnigiriInfoDialog', side_effect=RuntimeError('dialog unavailable')):
 with patch.object(notifications.QMessageBox, 'exec', lambda box: seen.append((box.text(), box.informativeText(), box.iconPixmap().isNull()))):
  notifications._native_show_info('Keep these technical details', title='Warning')
assert seen == [('Onigiri · Warning', 'Keep these technical details', False)]
print('PASS: fallback retains the Onigiri name, logo, and warning details.')
