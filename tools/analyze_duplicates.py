#!/usr/bin/env python3

import os
from collections import defaultdict
from pathlib import Path


def parse_test_plan_file(filepath):
    """Parse a test-plan.pxu file and extract id/name pairs."""
    plans = []
    current_plan = {}
    is_test_plan_unit = False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Unit field to detect test plan sections
                if line.startswith("unit:") and "test plan" in line:
                    is_test_plan_unit = True

                # Start of new test plan
                elif line.startswith("id:"):
                    if current_plan and "id" in current_plan:
                        plans.append(current_plan)
                    current_plan = {"id": line[3:].strip()}
                    current_plan["line_num"] = line_num
                    current_plan["is_test_plan"] = is_test_plan_unit
                    is_test_plan_unit = False

                # Name field
                elif line.startswith("_name:"):
                    current_plan["name"] = line[6:].strip()

            # Add the last plan
            if current_plan and "id" in current_plan:
                plans.append(current_plan)

    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    # Filter only test plans with names
    return [p for p in plans if p.get("is_test_plan") and p.get("name")]


def find_duplicates(plans):
    """Find duplicate names within the plans (case insensitive)."""
    name_to_plans = defaultdict(list)

    for plan in plans:
        name_lower = plan["name"].lower()
        name_to_plans[name_lower].append(plan)

    # Return only groups with duplicates
    duplicates = {}
    for name_lower, plan_list in name_to_plans.items():
        if len(plan_list) > 1:
            duplicates[name_lower] = plan_list

    return duplicates


def analyze_file(filepath):
    """Analyze a single file for duplicates."""
    plans = parse_test_plan_file(filepath)
    duplicates = find_duplicates(plans)

    results = {
        "file": filepath, 
        "total_plans": len(plans), 
        "duplicates": duplicates
    }

    return results


def main():
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent / "providers"

    # Find all test-plan.pxu files
    test_plan_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "test-plan.pxu":
                test_plan_files.append(os.path.join(root, file))

    files_with_duplicates = []

    # Analyze each file
    for filepath in sorted(test_plan_files):
        result = analyze_file(filepath)
        if result["duplicates"]:
            files_with_duplicates.append(result)

    # Report results
    print("=== DUPLICATE NAME ANALYSIS ===\n")

    if not files_with_duplicates:
        print("No duplicate names found in any test-plan.pxu files.")
    else:
        for result in files_with_duplicates:
            print(f"File: {result['file']}")
            print("Duplicates found:")

            for name_lower, plans in result["duplicates"].items():
                # Get the original name (with proper case) from first occurrence
                original_name = plans[0]["name"]
                print(f'- Name: "{original_name}" (case insensitive)')
                ids = [f"{p['id']} (line {p['line_num']})" for p in plans]
                print(f"  IDs: {', '.join(ids)}")
            print()


if __name__ == "__main__":
    main()
