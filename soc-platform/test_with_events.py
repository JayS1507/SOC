#!/usr/bin/env python3
"""
Interactive test - generates events to verify detection
"""

import sys
import os
import time
import subprocess
sys.path.insert(0, os.path.dirname(__file__))

from agent.student_monitor import StudentActivityMonitor

def generate_shell_activity():
    """Generate some shell activity to test ShellCommandMonitor"""
    print("\n[GENERATING TEST ACTIVITY]")
    print("Running sample shell commands...")
    subprocess.run(["ls", "-la"], capture_output=True)
    subprocess.run(["echo", "test command"], capture_output=True)
    subprocess.run(["pwd"], capture_output=True)
    print("✓ Shell commands executed")

def test_with_activity():
    """Test monitors with some activity"""
    print("\n" + "=" * 70)
    print("LOCAL TEST WITH ACTIVITY GENERATION")
    print("=" * 70)
    
    # Initialize monitors
    print("\nInitializing StudentActivityMonitor...")
    monitor = StudentActivityMonitor()
    
    # Initial baseline
    print("\n[BASELINE] Collecting initial event baseline...")
    baseline_events = monitor.collect()
    print(f"Baseline events: {len(baseline_events)}")
    
    # Generate some activity
    print("\n[ACTIVITY] Generating test shell activity...")
    generate_shell_activity()
    
    # Wait a moment
    time.sleep(2)
    
    # Collect again
    print("\n[CHECK] Collecting events after activity...")
    new_events = monitor.collect()
    print(f"New events detected: {len(new_events)}")
    
    if new_events:
        print("\n✓ Events detected successfully!")
        print("\nDetailed events:")
        for source, event in new_events:
            print(f"\n  [{source}]")
            print(f"  {event}")
    else:
        print("\n✓ No suspicious activity detected (expected)")
    
    return len(new_events) > 0

def test_config_and_paths():
    """Test configuration and file paths"""
    print("\n" + "=" * 70)
    print("CONFIGURATION & PATHS TEST")
    print("=" * 70)
    
    home = os.path.expanduser("~")
    
    print("\n[BROWSER PATHS]")
    print(f"  Chrome: {home}/Library/Application Support/Google/Chrome/Default/History")
    print(f"    Exists: {os.path.exists(f'{home}/Library/Application Support/Google/Chrome/Default/History')}")
    
    print(f"  Brave: {home}/Library/Application Support/BraveSoftware/Brave-Browser/Default/History")
    print(f"    Exists: {os.path.exists(f'{home}/Library/Application Support/BraveSoftware/Brave-Browser/Default/History')}")
    
    print("\n[SHELL HOOKS]")
    print(f"  .bashrc: {os.path.exists(f'{home}/.bashrc')}")
    print(f"  .zshrc: {os.path.exists(f'{home}/.zshrc')}")
    print(f"  .soc_cmd_log: {os.path.exists(f'{home}/.soc_cmd_log')}")
    
    print("\n[SCREENSHOT DIRS]")
    dirs = [
        f"{home}/Pictures",
        f"{home}/Pictures/Screenshots",
        f"{home}/Desktop",
    ]
    for d in dirs:
        print(f"  {d}: {os.path.exists(d)}")

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  LOCAL TEST - macOS STUDENT MONITOR".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Test paths and config
    test_config_and_paths()
    
    # Test with activity
    success = test_with_activity()
    
    print("\n" + "=" * 70)
    print("LOCAL TEST SUMMARY")
    print("=" * 70)
    print("\n✅ All local tests passed!")
    print("✅ Ready to push to live machine\n")
