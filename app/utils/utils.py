import re
from typing import Optional, Any

def parse_price_to_float(price_str: Optional[str]):
    if not price_str:
        return None
    m = re.findall(r"[\d\s.,]+", price_str)
    if not m:
        return None
    s = "".join(m)
    s = s.replace(" ", "").replace("\xa0", "")
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def perfume_to_dict_obj(obj: Any):
    fields = ["id", "title", "brand", "actual_price", "old_price", "url"]
    return {f: getattr(obj, f, None) for f in fields}