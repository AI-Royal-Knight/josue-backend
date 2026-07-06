lines_data = None
try:
    total_amount = sum(
        (float(l.get("labour") or 0) + float(l.get("material") or 0)) * float(l.get("qty") or 1)
        for l in lines_data
    )
except Exception as e:
    print(repr(e))
