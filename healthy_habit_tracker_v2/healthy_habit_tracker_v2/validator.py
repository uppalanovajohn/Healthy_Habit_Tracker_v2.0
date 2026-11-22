from datetime import datetime
from typing import Tuple, Optional
from models import HABIT_RULES
from logger_config import setup_logger

logger = setup_logger()

def validate_record_fields(date_str: str, category: str, value_raw: str) -> Tuple[bool, Optional[dict], str]:
    """Validates a single record across CLI, GUI, JSON, and bulk CSV imports."""
    cat = str(category).strip().lower()
    if cat not in HABIT_RULES:
        msg = f"Invalid category '{category}'. Allowed: {', '.join(HABIT_RULES.keys())}"
        logger.warning("Validation failed: %s", msg)
        return False, None, msg

    try:
        datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
    except ValueError:
        msg = f"Invalid date '{date_str}'. Expected YYYY-MM-DD."
        logger.warning("Validation failed: %s", msg)
        return False, None, msg

    try:
        val = float(value_raw)
    except (ValueError, TypeError):
        msg = f"Non-numeric value '{value_raw}'."
        logger.warning("Validation failed: %s", msg)
        return False, None, msg

    rules = HABIT_RULES[cat]
    if not (rules["min"] <= val <= rules["max"]):
        msg = f"Value {val} out of bounds for {cat} ({rules['min']}-{rules['max']})."
        logger.warning("Validation failed: %s", msg)
        return False, None, msg

    return True, {"date": str(date_str).strip(), "category": cat, "value": val}, ""

def prompt_category() -> str:
    valid = list(HABIT_RULES.keys())
    while True:
        choice = input(f"Select habit ({'/'.join(valid)}): ").strip().lower()
        if choice in valid:
            return choice
        print(f"  [!] Invalid category. Choose from: {', '.join(valid)}")

def prompt_value(category: str) -> float:
    rules = HABIT_RULES[category]
    while True:
        raw = input(f"Enter {category} ({rules['unit']}, {rules['min']:.0f}-{rules['max']:.0f}): ").strip()
        try:
            val = float(raw)
            if rules["min"] <= val <= rules["max"]:
                return val
            print(f"  [!] Out of range. Must be between {rules['min']} and {rules['max']}.")
        except ValueError:
            print("  [!] Invalid input. Please enter a numeric value.")

def prompt_date() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    while True:
        raw = input(f"Enter date (YYYY-MM-DD) [Press Enter for {today}]: ").strip()
        if not raw:
            return today
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            print("  [!] Invalid date format. Use YYYY-MM-DD.")
