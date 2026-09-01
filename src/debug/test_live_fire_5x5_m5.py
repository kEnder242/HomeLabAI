"""
[BKM-050] 5x5 GAUNTLET MANDATE:
⚠️ FORBIDDEN / DEPRECATED: Short back-to-back 50-second test scripts MUST NOT be used under the name '5x5'.
The 5x5 Gauntlet is ALWAYS a 75-minute live Playwright integration endurance test
moving through staged quiescence wait intervals: 0m -> 5m -> 10m -> 20m -> 40m (75 minutes total).

To run the authentic 5x5 Gauntlet, execute:
    python3 src/debug/test_perf_5x5_timed.py --intervals 0 5 10 20 40
"""
import sys

if __name__ == "__main__":
    print("=" * 80)
    print("❌ ERROR: Short 50-second test scripts are STRICTLY FORBIDDEN under the name '5x5'!")
    print("   The 5x5 Gauntlet is ALWAYS a 75-minute live Playwright integration test")
    print("   moving through staged quiescence wait intervals: 0m -> 5m -> 10m -> 20m -> 40m.")
    print("   To run the authentic 5x5 Gauntlet, execute:")
    print("     python3 src/debug/test_perf_5x5_timed.py --intervals 0 5 10 20 40")
    print("=" * 80)
    sys.exit(1)
