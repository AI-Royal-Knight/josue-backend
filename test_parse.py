def safe_float(val, default=0):
    try:
        if val is None or str(val).strip() == "":
            return float(default)
        return float(val)
    except (ValueError, TypeError):
        return float(default)

print(safe_float(None))
print(safe_float(""))
print(safe_float(" "))
print(safe_float("NaN"))
print(safe_float("1.5"))
