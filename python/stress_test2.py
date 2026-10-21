import pandas as pd
from classify_text import classify

dev = [
    ("driver took forever to arrive", "late_delivery"),
    ("they forgot my drinks", "missing_items"),
    ("the biryani was cold and soggy", "food_quality"),
    ("the rider shouted at me", "rider_behaviour"),
    ("order is incomplete", "missing_items"),
    ("was billed twice for one meal", "payment_issue"),
]

# Fresh test set, written by you or me BEFORE looking at the new rules' results
test = [
    ("my groceries never showed up", "missing_items"),
    ("the delivery guy was rude to me", "rider_behaviour"),
    ("took ages to get here", "late_delivery"),
    ("got a different dish than I ordered", "wrong_item"),
    ("money was taken twice from my card", "payment_issue"),
    ("the app froze when I tried to pay", "app_account"),
    ("one of my items was forgotten", "missing_items"),
    ("bread was mouldy", "food_quality"),
    ("order came 40 minutes behind schedule", "late_delivery"),
    ("couldn't apply my voucher", "app_account"),
]

for name, data in [("DEV", dev), ("FRESH TEST", test)]:
    d = pd.DataFrame(data, columns=["text", "truth"])
    d["predicted"] = d.text.map(classify)
    print(f"{name}: {(d.truth == d.predicted).sum()} / {len(d)} correct")
    print(d[d.truth != d.predicted].to_string(index=False), "\n")