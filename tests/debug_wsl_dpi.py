
import subprocess

# Trying SetProcessDpiAwareness (ShCore.dll)
# 0 = Unaware, 1 = System, 2 = PerMonitor
PS_SCRIPT = """
try {
    $code = @'
    using System;
    using System.Runtime.InteropServices;
    public class DPI {
        [DllImport("shcore.dll")]
        public static extern int SetProcessDpiAwareness(int value);
    }
'@
    Add-Type -TypeDefinition $code -Language CSharp
    [DPI]::SetProcessDpiAwareness(2) # PerMonitorAware
} catch {
    Write-Output "DPI Call Failed: $($_.Exception.Message)"
}

Add-Type -AssemblyName System.Windows.Forms
$screens = [System.Windows.Forms.Screen]::AllScreens
foreach ($s in $screens) {
    Write-Output "Device: $($s.DeviceName)"
    Write-Output "Bounds: $($s.Bounds)"
}
"""

def debug_dpi():
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as tf:
        tf.write(PS_SCRIPT)
        tf_name = tf.name
    
    try:
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", tf_name]
        print(f"Running DPI debug script...")
        # Don't decode automatically
        proc = subprocess.run(cmd, capture_output=True)
        
        # Try decoding with errors='ignore' which handles mixed encodings better than strict
        stdout = proc.stdout.decode('utf-8', errors='ignore')
        if not stdout.strip():
             stdout = proc.stdout.decode('utf-16', errors='ignore') # Try UTF-16
             
        print(stdout)
        
        stderr = proc.stderr.decode('utf-8', errors='ignore')
        if stderr:
            print("STDERR:", stderr)
        
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)

if __name__ == "__main__":
    debug_dpi()
