
from datetime import datetime, timezone, timedelta

def test_timezone_bug():
    # Simulate User Input: 17:21 UTC+8 (05:21 PM)
    # This is what Pydantic receives
    tz_makassar = timezone(timedelta(hours=8))
    user_input = datetime(2026, 1, 25, 17, 21, 0, tzinfo=tz_makassar)
    
    print(f"User Input (Local): {user_input}")
    print(f"User Input (UTC):   {user_input.astimezone(timezone.utc)}")
    
    # CURRENT BUGGY LOGIC
    buggy_time = user_input.replace(tzinfo=None) # Strips TZ, keeps 17:21
    print(f"Buggy Logic (Naive): {buggy_time}")
    
    # Scheduler Logic (Treats Naive as UTC)
    scheduler_trigger = buggy_time.replace(tzinfo=timezone.utc)
    print(f"Scheduler Trigger:  {scheduler_trigger}")
    
    # Real UTC time
    real_utc = user_input.astimezone(timezone.utc)
    
    diff = scheduler_trigger - real_utc
    print(f"Difference: {diff}")
    
    if diff.total_seconds() != 0:
        print("❌ BUG CONFIRMED: Scheduler trigger is wrong!")
    else:
        print("✅ NO BUG")

    # PROPOSED FIX
    print("\nTesting Fix...")
    fixed_time = user_input.astimezone(timezone.utc).replace(tzinfo=None)
    print(f"Fixed Logic (Naive): {fixed_time}")
    
    scheduler_trigger_fixed = fixed_time.replace(tzinfo=timezone.utc)
    print(f"Fixed Trigger:      {scheduler_trigger_fixed}")
    
    diff_fixed = scheduler_trigger_fixed - real_utc
    if diff_fixed.total_seconds() == 0:
        print("✅ FIX VERIFIED: Trigger matches real UTC time")

if __name__ == "__main__":
    test_timezone_bug()
