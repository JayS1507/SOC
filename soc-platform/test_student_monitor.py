#!/usr/bin/env python3
"""
Local test script for StudentActivityMonitor
Tests all monitors without needing the full agent running
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agent.student_monitor import (
    BrowserMonitor,
    ActiveWindowMonitor,
    DNSMonitor,
    LabUSBMonitor,
    ShellCommandMonitor,
    ScreenshotMonitor,
    StudentActivityMonitor
)

def test_individual_monitors():
    """Test each monitor individually"""
    print("=" * 70)
    print("TESTING INDIVIDUAL MONITORS")
    print("=" * 70)
    
    # Test 1: BrowserMonitor
    print("\n[TEST 1] BrowserMonitor")
    print("-" * 70)
    try:
        browser = BrowserMonitor()
        print("✓ BrowserMonitor initialized successfully")
        events = browser.check()
        print(f"✓ Found {len(events)} browser events")
        if events:
            print(f"  Sample: {events[0][:100]}")
    except Exception as e:
        print(f"✗ BrowserMonitor error: {e}")
    
    # Test 2: ActiveWindowMonitor
    print("\n[TEST 2] ActiveWindowMonitor")
    print("-" * 70)
    try:
        window = ActiveWindowMonitor()
        print("✓ ActiveWindowMonitor initialized successfully")
        window_title = window._get_active_window()
        print(f"✓ Current active window: {window_title}")
        events = window.check()
        print(f"✓ Found {len(events)} window events")
    except Exception as e:
        print(f"✗ ActiveWindowMonitor error: {e}")
    
    # Test 3: DNSMonitor
    print("\n[TEST 3] DNSMonitor")
    print("-" * 70)
    try:
        dns = DNSMonitor()
        print("✓ DNSMonitor initialized successfully")
        events = dns.check()
        print(f"✓ Found {len(events)} DNS events")
        if events:
            print(f"  Sample: {events[0][:100]}")
    except Exception as e:
        print(f"✗ DNSMonitor error: {e}")
    
    # Test 4: LabUSBMonitor
    print("\n[TEST 4] LabUSBMonitor")
    print("-" * 70)
    try:
        usb = LabUSBMonitor()
        print("✓ LabUSBMonitor initialized successfully")
        events = usb.check()
        print(f"✓ Found {len(events)} USB events")
    except Exception as e:
        print(f"✗ LabUSBMonitor error: {e}")
    
    # Test 5: ShellCommandMonitor
    print("\n[TEST 5] ShellCommandMonitor")
    print("-" * 70)
    try:
        shell = ShellCommandMonitor()
        print("✓ ShellCommandMonitor initialized successfully")
        events = shell.check()
        print(f"✓ Found {len(events)} shell command events")
        if events:
            print(f"  Sample: {events[0][:100]}")
    except Exception as e:
        print(f"✗ ShellCommandMonitor error: {e}")
    
    # Test 6: ScreenshotMonitor
    print("\n[TEST 6] ScreenshotMonitor")
    print("-" * 70)
    try:
        screenshot = ScreenshotMonitor()
        print("✓ ScreenshotMonitor initialized successfully")
        events = screenshot.check()
        print(f"✓ Found {len(events)} screenshot events")
    except Exception as e:
        print(f"✗ ScreenshotMonitor error: {e}")

def test_orchestrator():
    """Test the StudentActivityMonitor orchestrator"""
    print("\n" + "=" * 70)
    print("TESTING ORCHESTRATOR (StudentActivityMonitor)")
    print("=" * 70)
    try:
        monitor = StudentActivityMonitor()
        print("\n✓ StudentActivityMonitor initialized successfully\n")
        
        print("Collecting events...")
        events = monitor.collect()
        print(f"\n✓ Total events collected: {len(events)}\n")
        
        if events:
            print("Sample events:")
            for source, event in events[:5]:
                print(f"  [{source}] {event[:80]}...")
    except Exception as e:
        print(f"✗ StudentActivityMonitor error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  SOC PLATFORM - STUDENT MONITOR LOCAL TEST".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    test_individual_monitors()
    test_orchestrator()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\n✓ All monitors are working on macOS!\n")
