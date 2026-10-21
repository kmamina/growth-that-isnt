import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline, make_union
from sklearn.metrics import accuracy_score
from config import ROOT

lab = pd.read_csv(ROOT / "reports" / "label_sample_clean.csv")

def build():
    feats = make_union(
        TfidfVectorizer(ngram_range=(1, 2), lowercase=True),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True))
    return make_pipeline(feats, LogisticRegression(max_iter=2000, C=10))

# 1. leave-sentences-out cross-validation (no sentence appears in both train and test)
pred = cross_val_predict(build(), lab.complaint_text, lab.my_label,
                         cv=GroupKFold(n_splits=5), groups=lab.complaint_text)
print("Unseen-sentence CV accuracy on the 100 labels: %.1f%%"
      % (100 * accuracy_score(lab.my_label, pred)))
print("(rider_behaviour has one distinct sentence, so it is always held out and missed.)")

# 2. paraphrase sets
dev = [("driver took forever to arrive", "late_delivery"), ("they forgot my drinks", "missing_items"),
       ("the biryani was cold and soggy", "food_quality"), ("the rider shouted at me", "rider_behaviour"),
       ("order is incomplete", "missing_items"), ("was billed twice for one meal", "payment_issue")]
test = [("my groceries never showed up", "missing_items"), ("the delivery guy was rude to me", "rider_behaviour"),
        ("took ages to get here", "late_delivery"), ("got a different dish than I ordered", "wrong_item"),
        ("money was taken twice from my card", "payment_issue"), ("the app froze when I tried to pay", "app_account"),
        ("one of my items was forgotten", "missing_items"), ("bread was mouldy", "food_quality"),
        ("order came 40 minutes behind schedule", "late_delivery"), ("couldn't apply my voucher", "app_account")]

model = build().fit(lab.complaint_text, lab.my_label)
for name, data in [("DEV paraphrases", dev), ("FRESH paraphrases", test)]:
    d = pd.DataFrame(data, columns=["text", "truth"])
    d["predicted"] = model.predict(d.text)
    print(f"\nTF-IDF {name}: {(d.truth == d.predicted).sum()} / {len(d)} correct")
    print(d[d.truth != d.predicted].to_string(index=False))

# 3. agreement with the rules on all tickets that have text
t = pd.read_csv(ROOT / "reports" / "ticket_themes.csv")
t = t[t.theme != "no_text"].copy()
t["tfidf"] = model.predict(t.complaint_text)
print("\nAgreement with rules on %d tickets: %.1f%%" % (len(t), 100 * (t.tfidf == t.theme).mean()))
print("Missing-item tickets: rules %d | TF-IDF %d" % ((t.theme == "missing_items").sum(),
                                                       (t.tfidf == "missing_items").sum()))
t.to_csv(ROOT / "reports" / "ticket_themes_tfidf.csv", index=False)