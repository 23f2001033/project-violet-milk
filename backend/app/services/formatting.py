"""
Indian numeric formatting.  Owner: BE3

Python's "{:,}" produces Western grouping (470,000). Indian financial and legal
documents use the lakh/crore convention (4,70,000) - the frontend already
renders it that way via en-IN, and a dossier that disagrees with the screen
looks like a different case file to the officer reading it.
"""


def inr_group(value: float | int) -> str:
    """Group digits Indian-style: last three, then pairs.

    470000    -> 4,70,000
    12345678  -> 1,23,45,678
    """
    neg = value < 0
    whole = f"{abs(int(round(value)))}"

    if len(whole) <= 3:
        grouped = whole
    else:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail

    return ("-" if neg else "") + grouped


def inr(value: float | int) -> str:
    """Rupee amount with the currency code, e.g. 'INR 4,70,000'."""
    return f"INR {inr_group(value)}"
