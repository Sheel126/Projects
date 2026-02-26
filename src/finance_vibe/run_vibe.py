import subprocess
import sys
import os


def run_workflow():
    # 1. CLIMB TO ROOT: This script is in src/finance_vibe/, so root is 2 levels up
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
    SRC_DIR = os.path.join(ROOT_DIR, "src")

    # 2. ENVIRONMENT SETUP
    # Set PYTHONPATH to 'src' so 'from finance_vibe import config' works in sub-processes
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")

    # 3. SCRIPT PATHS (Relative to the Project Root)
    scripts = [
        "src/finance_vibe/ticker_provider.py",
        "src/finance_vibe/data_ingestor.py",
        "src/finance_vibe/analysis_engine_local.py",
        "src/finance_vibe/swing_scanner.py"
    ]

    print(f"🚀 Starting Finance-Vibe Pipeline...")
    print(f"📍 Project Root: {ROOT_DIR}\n")

    for script in scripts:
        # Construct the absolute path to each script from the Project Root
        script_path = os.path.join(ROOT_DIR, script)

        print(f"🔹 Running: {script}...")
        try:
            # We set 'cwd=ROOT_DIR' so scripts looking for 'data/' find it correctly
            subprocess.run([sys.executable, script_path],
                           check=True, env=env, cwd=ROOT_DIR)
            print(f"✅ Finished: {script}\n")
        except subprocess.CalledProcessError:
            print(f"❌ Error in {script}. Pipeline halted.")
            sys.exit(1)

    print("🏁 Workflow Complete!")
    print(f"📁 Reports saved to: {os.path.join(ROOT_DIR, 'data/logs/')}")


if __name__ == "__main__":
    run_workflow()
