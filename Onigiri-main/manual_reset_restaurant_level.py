"""
Manual Restaurant Level Reset Script
Run this from Anki's debug console: Tools → Debug Console
Then paste this code and press Ctrl+Return (or Cmd+Return on Mac)
"""

from aqt import mw
import os
import json

# Reset in Anki config
config = mw.addonManager.getConfig('1011095603')
if config and 'achievements' in config:
    if 'restaurant_level' not in config['achievements']:
        config['achievements']['restaurant_level'] = {}
    
    config['achievements']['restaurant_level']['total_xp'] = 0
    config['achievements']['restaurant_level']['level'] = 0
    
    mw.addonManager.writeConfig('1011095603', config)
    print("✓ Config updated - Level and XP reset to 0")
else:
    print("✗ Could not find config")

# Reset in gamification.json
addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
gamification_file = os.path.join(addon_path, 'user_files', 'gamification.json')

try:
    with open(gamification_file, 'r+', encoding='utf-8') as f:
        data = json.load(f)
        if 'restaurant_level' in data:
            data['restaurant_level']['level'] = 0
            data['restaurant_level']['total_xp'] = 0
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
            print("✓ gamification.json updated")
        else:
            print("✗ restaurant_level not found in gamification.json")
except Exception as e:
    print(f"✗ Error updating gamification.json: {e}")

# Force collection save
if mw.col:
    mw.col.setMod()
    print("✓ Collection marked as modified")

# Refresh UI
mw.reset()
print("✓ UI refreshed")

print("\n=== RESET COMPLETE ===")
print("Your Restaurant Level should now be 0")
