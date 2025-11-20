#!/usr/bin/env python
"""
Quick threading test to verify Event() behavior
"""
import threading
import time

print("Testing threading.Event() behavior...")

wake_event = threading.Event()

def listener_thread():
    """Simulates the listener thread"""
    time.sleep(2)  # Simulate waiting
    print("[Listener] Detected wake word, setting event...", flush=True)
    wake_event.set()
    print("[Listener] Event set successfully!", flush=True)

def orchestrator_thread():
    """Simulates the orchestrator thread"""
    print("[Orchestrator] Waiting for wake word...", flush=True)
    print(f"[Orchestrator] Event state before wait: {wake_event.is_set()}", flush=True)
    wake_event.wait()
    print("[Orchestrator] Wake word received!", flush=True)
    wake_event.clear()
    print("[Orchestrator] Done!", flush=True)

# Start both threads
listener = threading.Thread(target=listener_thread, daemon=True)
orchestrator = threading.Thread(target=orchestrator_thread, daemon=True)

listener.start()
orchestrator.start()

# Wait for both to complete
listener.join(timeout=5)
orchestrator.join(timeout=5)

if orchestrator.is_alive():
    print("❌ FAILED: Orchestrator thread is still blocked!")
else:
    print("✅ SUCCESS: Threading works correctly!")
