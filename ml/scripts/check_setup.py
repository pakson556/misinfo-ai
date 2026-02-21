#!/usr/bin/env python3
"""
Quick check to verify the directory structure is correct.
"""
from pathlib import Path

def main():
    """Check ml/ directory structure."""
    base = Path(__file__).parent.parent  # ml/
    
    print("🔍 Checking directory structure...")
    print(f"Base directory: {base.absolute()}")
    print()
    
    # Check all required directories
    dirs_to_check = [
        "api",
        "training", 
        "scripts",
        "tests",
        "data/raw",
        "data/processed",
        "data/logs",
        "data/models",
    ]
    
    all_good = True
    for d in dirs_to_check:
        path = base / d
        if path.exists():
            print(f"✅ {d}/")
        else:
            print(f"❌ {d}/ - MISSING")
            all_good = False
    
    print()
    if all_good:
        print("✅ All directories created successfully!")
        print("\nNext steps:")
        print("1. Place your raw data files in: ml/data/raw/")
        print("2. Run: python -m ml.training.prepare_data")
    else:
        print("❌ Some directories are missing.")
        print("Run: ./setup.sh to create the full structure")

if __name__ == "__main__":
    main()