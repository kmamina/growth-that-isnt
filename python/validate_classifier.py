import re
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from config import ROOT
from classify_text import classify

pd.set_option("display.width", 170)

lab = pd.read_csv(ROOT / "reports" / "label_sample_clean.csv")
lab["predicted"] = lab.complaint_text.map(classify)

print("Accuracy on 100 hand-labelled tickets: %.1f%%" % (100 * accuracy_score(lab.my_label, lab.predicted)))
print("\nPer-theme precision / recall:")
print(classification_report(lab.my_label, lab.predicted, zero_division=0))

themes = sorted(set(lab.my_label) | set(lab.predicted))
print("Confusion matrix (rows = my label, columns = classifier):")
print(pd.DataFrame(confusion_matrix(lab.my_label, lab.predicted, labels=themes),
                   index=themes, columns=themes))

err = lab[lab.my_label != lab.predicted]
print("\nDisagreements:", len(err))
print(err[["complaint_text", "my_label", "predicted"]].to_string(index=False))

# ---- stress test: messier, paraphrased complaints written by hand ----
stress = [
    ("my bag was missing 2 things", "missing_items"),
    ("driver took forever to arrive", "late_delivery"),
    ("they forgot my drinks", "missing_items"),
    ("got charged 2x", "payment_issue"),
    ("the biryani was cold and soggy", "food_quality"),
    ("nobody told me my order was delayed", "late_delivery"),
    ("the rider shouted at me", "rider_behaviour"),
    ("order is incomplete", "missing_items"),
    ("was billed twice for one meal", "payment_issue"),
    ("received a burger instead of a pizza", "wrong_item"),
    ("app keeps freezing at checkout", "app_account"),
    ("half of my order never showed up", "missing_items"),
]
s = pd.DataFrame(stress, columns=["text", "truth"])
s["predicted"] = s.text.map(classify)
print("\nSTRESS TEST on paraphrases: %d / %d correct" % ((s.truth == s.predicted).sum(), len(s)))
print(s[s.truth != s.predicted].to_string(index=False))

lab.to_csv(ROOT / "reports" / "classifier_validation.csv", index=False)