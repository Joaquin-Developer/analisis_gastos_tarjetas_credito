from datetime import datetime


def get_actual_month() -> str:
    return datetime.now().strftime("%B, %Y")


def month_str_to_month_name(month_str: str) -> str:
    date = datetime.strptime(month_str, "%Y-%m")
    return date.strftime("%B, %Y")
