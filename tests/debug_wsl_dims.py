
import subprocess
import json

PS_SCRIPT = """
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$info = @{
    VirtualScreen = [System.Windows.Forms.SystemInformation]::VirtualScreen
    PrimaryScreen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    AllScreens = @()
}

foreach ($s in [System.Windows.Forms.Screen]::AllScreens) {
    $info.AllScreens += @{
        DeviceName = $s.DeviceName
        Bounds = $s.Bounds
        WorkingArea = $s.WorkingArea
        Primary = $s.Primary
    }
}

Write-Output ($info | ConvertTo-Json -Depth 2)
"""

def debug_wsl_dims():
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as tf:
        tf.write(PS_SCRIPT)
        tf_name = tf.name
    
    try:
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", tf_name]
        print(f"Running debug script on {tf_name}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode != 0:
            print("PowerShell Error:", proc.stderr)
            return

        print("--- PowerShell Output ---")
        print(proc.stdout)
        print("-----------------------")
        
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)

if __name__ == "__main__":
    debug_wsl_dims()
