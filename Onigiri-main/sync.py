import os
import zipfile
import shutil
import time
import json
from pathlib import Path
from aqt import mw
from . import config

class SyncManager:
    """
    Manages zipping and unzipping of Onigiri user data into Anki's media folder
    to allow synchronization via AnkiWeb.
    """

    def __init__(self):
        self._sync_filename = None
        self._media_dir = None
        self._user_files_dir = os.path.join(os.path.dirname(__file__), "user_files")
        self._state_file = os.path.join(os.path.dirname(__file__), ".onigiri_sync_state.json")

    def _ensure_init(self):
        """Initialize paths that depend on the active profile."""
        if not mw.col:
            return False
        
        profile_name = mw.pm.name
        self._sync_filename = f"_onigiri_sync_{profile_name}.zip"
        self._media_dir = mw.col.media.dir()
        return True

    def _load_state(self):
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"last_zip_mtime": {}, "last_zip_size": {}}

    def _save_state(self, mtime, size):
        if not self._ensure_init():
            return
        
        state = self._load_state()
        profile_name = mw.pm.name
        
        state["last_zip_mtime"][profile_name] = mtime
        state["last_zip_size"][profile_name] = size
        
        try:
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except:
            pass

    def is_enabled(self):
        return config.get_config().get("ankiweb_sync_enabled", False)

    def get_sync_file_path(self):
        if not self._ensure_init():
            return None
        return os.path.join(self._media_dir, self._sync_filename)

    def pack_user_files(self):
        """Zips the user_files directory into the media folder."""
        if not self._ensure_init():
            return False

        sync_path = self.get_sync_file_path()
        temp_zip = sync_path + ".tmp"

        try:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(self._user_files_dir):
                    for file in files:
                        # Skip temporary files or logs if any
                        if file.endswith(".log"):
                            continue
                            
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, self._user_files_dir)
                        zf.write(file_path, rel_path)
            
            # Atomic swap
            if os.path.exists(sync_path):
                os.remove(sync_path)
            os.rename(temp_zip, sync_path)
            
            # Update state
            stat = os.stat(sync_path)
            self._save_state(stat.st_mtime, stat.st_size)
            
            return True
        except Exception as e:
            print(f"Onigiri Sync: Failed to pack files: {e}")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False

    def unpack_user_files(self):
        """Unzips the sync file from the media folder into user_files."""
        if not self._ensure_init():
            return False

        sync_path = self.get_sync_file_path()
        if not os.path.exists(sync_path):
            return False

        try:
            # Create a backup of current user_files just in case
            backup_dir = self._user_files_dir + "_backup"
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            
            # Extract to a temp directory first
            temp_extract = self._user_files_dir + "_incoming"
            if os.path.exists(temp_extract):
                shutil.rmtree(temp_extract)
            os.makedirs(temp_extract)

            with zipfile.ZipFile(sync_path, 'r') as zf:
                zf.extractall(temp_extract)

            # Swap directories
            shutil.move(self._user_files_dir, backup_dir)
            shutil.move(temp_extract, self._user_files_dir)
            
            # Clean up backup
            shutil.rmtree(backup_dir)
            
            # Update state to reflect that we are in sync with this zip
            stat = os.stat(sync_path)
            self._save_state(stat.st_mtime, stat.st_size)
            
            return True
        except Exception as e:
            print(f"Onigiri Sync: Failed to unpack files: {e}")
            return False

    def get_local_mtime(self):
        """Get the latest modification time of any file in user_files."""
        latest = 0
        for root, _, files in os.walk(self._user_files_dir):
            for file in files:
                mtime = os.path.getmtime(os.path.join(root, file))
                if mtime > latest:
                    latest = mtime
        return latest

    def get_cloud_mtime(self):
        """Get the modification time of the sync file in the media folder."""
        sync_path = self.get_sync_file_path()
        if sync_path and os.path.exists(sync_path):
            return os.path.getmtime(sync_path)
        return 0

    def check_conflict(self):
        """
        Returns:
            'none': Data is the same or cloud doesn't exist.
            'local_newer': Local data has been modified more recently than cloud.
            'cloud_newer': Cloud data is newer than local.
        """
        if not self._ensure_init():
            return 'none'
            
        sync_path = self.get_sync_file_path()
        if not os.path.exists(sync_path):
            return 'none'
            
        # Get current file stats
        stat = os.stat(sync_path)
        curr_mtime = stat.st_mtime
        curr_size = stat.st_size
        
        # Get last known state
        state = self._load_state()
        profile_name = mw.pm.name
        last_mtime = state["last_zip_mtime"].get(profile_name, 0)
        last_size = state["last_zip_size"].get(profile_name, 0)
        
        # If the file hasn't changed since we last packed/unpacked it, there's no conflict
        # even if the zip is newer than the source files (which it always will be after a pack).
        if abs(curr_mtime - last_mtime) < 1.0 and curr_size == last_size:
            return 'none'
            
        # If it HAS changed, we compare times to see which direction to suggest
        local_time = self.get_local_mtime()
        
        # Give a 5-second buffer
        if curr_mtime > local_time + 5:
            return 'cloud_newer'
        elif local_time > curr_mtime + 5:
            return 'local_newer'
            
        return 'none'

# Singleton instance
onigiri_sync = SyncManager()

