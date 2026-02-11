import subprocess
import sys
import os
import importlib.util

def run_command(command, description):
    """
    Runs a shell command and prints the status.
    """
    print(f"📦 Processing: {description}...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ Completed: {description}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"   Error Log: {e.stderr}")

def check_system_dependencies():
    """
    Checks and installs system-level dependencies (e.g., FFmpeg).
    """
    print("\n🔧 [System] Checking system tools...")
    
    # Check FFmpeg (Crucial for audio processing)
    if shutil.which("ffmpeg") is None:
        print("⚠️ FFmpeg not found. Installing via apt-get...")
        run_command(['apt-get', 'update', '-qq'], "Update Package List")
        run_command(['apt-get', 'install', '-y', 'ffmpeg'], "Install FFmpeg")
    else:
        print("✅ FFmpeg is already installed.")

def install_python_requirements(req_path="requirements.txt"):
    """
    Installs Python libraries from requirements.txt.
    """
    print("\n🐍 [Python] Checking libraries...")
    
    if os.path.exists(req_path):
        print(f"📄 Found {req_path}. Installing dependencies...")
        # -q: Quiet mode (less logs), --upgrade: Ensure latest versions
        run_command([sys.executable, "-m", "pip", "install", "-r", req_path], "Pip Install Requirements")
    else:
        print(f"⚠️ Warning: {req_path} not found in current directory.")
        print("   Skipping bulk installation. Please check your file structure.")

def init_colab_env():
    """
    [Main Entry Point]
    Sets up the complete environment for Bass Separation.
    1. Install System Dependencies (FFmpeg)
    2. Install Python Dependencies (requirements.txt)
    3. Perform a final health check
    """
    print("🚀 Initializing Environment...")

    # 1. System Setup
    check_system_dependencies()

    # 2. Python Setup
    install_python_requirements()

    # 3. Health Check (Verify critical imports)
    print("\n🏥 Performing Health Check...")
    critical_libs = ["demucs", "torchaudio", "librosa", "museval"]
    missing = []
    
    for lib in critical_libs:
        if importlib.util.find_spec(lib) is None:
            missing.append(lib)
    
    if not missing:
        print("✅ All critical libraries are ready!")
    else:
        print(f"❌ Missing libraries: {', '.join(missing)}")
        print("   Try running '!pip install -r requirements.txt' manually.")

    print("\n🎉 Environment Setup Complete!")

# Need shutil for 'which' command
import shutil
