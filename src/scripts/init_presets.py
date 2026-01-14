import sys
import os
import shutil
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Use the config module logic
try:
    from src.config import GLOBAL_PRESET_DIR, ASSETS_DIR
except ImportError:
    # Failback/Setup for when running directly
    print("WARNING: Direct import failed, adjusting path manually.")
    sys.path.append(str(ROOT_DIR))
    from src.config import GLOBAL_PRESET_DIR, ASSETS_DIR

def init_presets():
    print(f"🔄 [Preset Init] Initializing Presets...")
    asset_preset_dir = ASSETS_DIR / "presets"
    
    if not asset_preset_dir.exists():
        print(f"⚠️ [Preset Init] Assets dir not found: {asset_preset_dir}")
        return

    GLOBAL_PRESET_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    skipped = 0
    for f in os.listdir(asset_preset_dir):
        if f.endswith(".json"):
            src = asset_preset_dir / f
            dst = GLOBAL_PRESET_DIR / f
            
            # Copy if not exists
            if not dst.exists():
                shutil.copy(src, dst)
                print(f"✅ [Preset Init] Installed: {f}")
                count += 1
            else:
                skipped += 1
                
    print(f"✨ [Preset Init] Complete ({count} installed, {skipped} existing skipped).")

if __name__ == "__main__":
    init_presets()
