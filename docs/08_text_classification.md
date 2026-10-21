# Phase 4 — Complaint Text Classification (Rule-Based NLP)

## Purpose

The Head of CX reported that customers were unhappy, but the existing ticket `category` field did not clearly explain why.

The goal of this phase was to classify the **actual complaint text** into meaningful operational themes and determine whether an important problem was being hidden inside the existing categories.

This phase also tests whether complaint text can reveal operational issues that are not visible from structured ticket categories alone.

---

## Dataset

The dataset contains **15,574 support tickets**.

- **14,011 tickets (90%)** contain complaint text.
- **1,563 tickets (10%)** have no complaint text and are reported separately as `no_text`.
- The complaint text is highly templated: there are only **36 distinct sentences** across the text-bearing tickets.

Because the text is highly repetitive, validation accuracy on the original tickets should **not** be interpreted as evidence that the classifier would perform equally well on natural, unseen customer language.

---

## Method

Two approaches were used as complementary checks.

### Classifier 1 — Ordered Keyword Rules

A transparent rule-based classifier was created using seven complaint themes:

| Label | Meaning |
|---|---|
| `late_delivery` | late, delayed, slow, long wait |
| `missing_items` | items missing, short, not in the bag, did not arrive |
| `wrong_item` | wrong item, someone else's order, wrong size |
| `food_quality` | stale, not fresh, leaking, damaged, tasted off |
| `payment_issue` | charged twice, wrong amount, failed payment, card refund |
| `app_account` | app crash, promo code, invoice, address, phone, order history, loyalty points |
| `rider_behaviour` | rider's manner, such as being impolite |
| `other_unclear` | does not match any of the above themes |

The rules are **ordered**, so more specific patterns are checked before broader ones.

For example, a complaint containing a clear payment phrase is classified as `payment_issue` before it can fall into `other_unclear`.

No paid API or LLM was used.

Therefore, this is a **rule-based NLP pipeline, not a GenAI system**.

---

### Classifier 2 — TF-IDF + Logistic Regression

A second classifier was created using:

- TF-IDF features
- Word n-grams
- Character n-grams
- Logistic regression

It was trained using the **100 manually labelled tickets** and used as an independent second opinion.

The purpose was not to claim that this was a production-ready machine-learning model, but to see whether a statistical text model produced a similar picture to the hand-built rules.

---

# Validation

## 100 Hand-Labelled Tickets

| Test | Rules | TF-IDF |
|---|---:|---:|
| 100 hand-labelled tickets | **100%** | **63%** |

The 100% result for the rules classifier needs to be interpreted carefully.

The complaint text is highly templated, and the rules were written after reviewing the available text. Therefore, this result demonstrates that the rules correctly captured the known patterns in this dataset; **it does not demonstrate generalisation to new customer language**.

The TF-IDF model achieved 63% under cross-validation where whole sentences were held out, giving a more realistic indication of its difficulty with unseen wording.

---

## Paraphrase Stress Testing

To test generalisation beyond the templated sentences, six development paraphrases and ten fresh paraphrases were created.

The development set was used to tune the rules.

The fresh set was kept separate and was **never used for tuning**.

| Test | Rules | TF-IDF |
|---|---:|---:|
| 100 hand-labelled tickets | 100% | 63% |
| Development paraphrases, before rule edits | 0/6 | n/a |
| Development paraphrases, after rule edits | **6/6** | 2/6 |
| Fresh paraphrases, before rule edits | 0/10 | n/a |
| Fresh paraphrases, after rule edits | **1/10** | 4/10 |

The gap between **6/6 on tuned phrases and 1/10 on fresh phrases** shows that tuning keywords to seen wording does not transfer reliably to new wording.

The rules did not assign a **wrong theme** on the paraphrase tests. Instead, when they did not recognise new wording, they returned `other_unclear`.

This means the rule system has **high precision but limited recall on unseen wording**.

The development/fresh split is important because it prevents the final test from being directly tuned to the rules.

---

## Label Review

The initial labels were reviewed once against the written labelling guide before the classifier's output was scored.

**26 incorrect labels were corrected**, primarily where tickets had originally been labelled `other_unclear` even though their complaint text clearly matched one of the defined themes.

---

# Hidden Theme — Missing Items

The most important finding from the text classification was a previously hidden **missing-items problem**.

The existing ticket categories did not reliably expose this issue.

### Key findings

| Measure | Result |
|---|---|
| Missing-item tickets filed under `other` | **72% in Q-1; 69% in Q0** |
| Share of `other` tickets that were actually missing items | **11.4% in Q-1; 21.7% in Q0** |
| Missing-item tickets per 100 grocery orders — Zone D, Q0 | **12.8** |
| Missing-item tickets per 100 grocery orders — Zone G, Q0 | **14.1** |
| Missing-item tickets per 100 grocery orders — other zones, Q0 | **1.2–2.6** |
| Q0 missing-item tickets from DarkStore_007 and DarkStore_013 | **55% combined** |

DarkStore_007 is in **Zone D** and generated **112 missing-item tickets** in Q0.

DarkStore_013 is in **Zone G** and generated **103 missing-item tickets**.

No other store generated more than **6** missing-item tickets.

---

## Business Interpretation

The Head of CX was correct that there was a meaningful customer problem hidden inside the existing ticket categories.

The text classification revealed that:

> **Missing-item complaints were being substantially hidden under the generic `other` category.**

More importantly, the problem was **not evenly distributed across the business**.

It was highly concentrated in:

- **Zone D → DarkStore_007**
- **Zone G → DarkStore_013**

This suggests a potential **store-level operational problem**, rather than a company-wide customer-service issue.

The finding is also distinct from the previously identified **delivery-lateness problem in Zones C and F**.

Therefore, the analysis points toward two different operational problems:

**Delivery lateness → Zones C and F**

**Missing items → DarkStore_007 and DarkStore_013 in Zones D and G**

This distinction matters because the two problems would require different operational responses.

The analysis changes the business question from:

> **"Why are customers unhappy?"**

to:

> **"Why are customers reporting missing items at DarkStore_007 and DarkStore_013, and what operational process is causing these failures?"**

That is a much more actionable question for the CX and operations teams.

---

# Second Opinion — Rules vs TF-IDF

The two classifiers agreed on **94.5% of the 14,011 tickets containing complaint text**.

### Missing-item detection

| Classifier | Missing-item tickets identified |
|---|---:|
| Rules | **1,157** |
| TF-IDF | **853** |

The TF-IDF model therefore identified approximately **26% fewer missing-item tickets** than the rules classifier.

The most likely reason is that the TF-IDF model was trained on only **100 labelled examples**, which is a very small training set for a text-classification problem.

Interestingly, TF-IDF performed slightly better on the small fresh-paraphrase stress test:

- TF-IDF: **4/10**
- Rules: **1/10** after tuning

However, these samples are extremely small, so this difference should **not** be treated as evidence that one approach is definitively better.

The more important result is that both approaches provided a useful cross-check, while the transparent rules made it easier to trace exactly why a complaint was classified as a particular theme.

---

# Limitations

### 1. The text is highly templated

There are only 36 distinct complaint sentences.

Therefore, the 100% rule accuracy on the existing tickets should not be interpreted as evidence that the classifier would achieve 100% accuracy on real-world, naturally written customer complaints.

---

### 2. Keyword rules have limited recall on unseen wording

The rules depend on known words and phrases.

When customers describe the same problem using completely different language, the classifier may fail to recognise it and place it into `other_unclear`.

Therefore, the current rule-based system is useful for this dataset but would likely **miss some real complaints in production**.

---

### 3. The TF-IDF model has too little training data

The TF-IDF model was trained using only **100 labelled tickets**.

A 63% result on unseen sentences demonstrates that the model does not yet have enough labelled examples to be considered reliable for production use.

---

### 4. The hidden-theme percentage is model-dependent

The analysis estimates that **69%–72% of missing-item tickets were hidden under `other`**.

However, this figure depends on the classification method used.

Because the rule-based classifier has imperfect recall on unseen wording, the true number of missing-item complaints could be higher. **The TF-IDF model's lower count (853 vs 1,157) also shows that the estimated volume moves with the classification method.**

The finding should therefore be treated as a **strong directional signal rather than an exact production measurement**.

---

### 5. The validation samples are small

The development set contains only six paraphrases and the fresh test contains only ten.

These tests are useful stress checks, but they are too small to provide a statistically strong estimate of real-world generalisation.

---

# Production Recommendation

For a production system, I would not rely on the current keyword rules or the 100-row TF-IDF model alone.

A stronger approach would be:

1. Manually label **thousands of representative tickets**.
2. Create a clearly defined labelling guide.
3. Train a supervised text-classification model on the labelled data.
4. Keep a separate held-out validation/test set.
5. Measure precision, recall and F1-score for each complaint theme.
6. Monitor `other_unclear` as a signal for new or changing complaint types.
7. Periodically review incorrectly classified tickets and retrain the model.
8. Alternatively, evaluate an LLM-based classifier against the same held-out labelled benchmark.

The important principle is that the model should be **validated against human-labelled data rather than trusted simply because it produces plausible labels**.

---

# Files Produced

- `python/classify_text.py` — ordered keyword-rules classifier
- `python/validate_classifier.py` — 100-label validation and initial stress test
- `python/stress_test2.py` — development and fresh paraphrase tests
- `python/hidden_theme.py` — hidden-theme analysis and charts
- `python/tfidf_model.py` — TF-IDF + logistic regression second opinion
- `reports/ticket_themes.csv` — rule-based classifications
- `reports/ticket_themes_tfidf.csv` — TF-IDF classifications
- `reports/label_sample_clean.csv` — reviewed labelled sample

### Charts

- `images/hidden_theme_overview.png`
- `images/hidden_theme_by_zone.png`
- `images/hidden_theme_by_store.png`

---

# Phase 4 Conclusion

The complaint text analysis uncovered a problem that was not visible from the existing ticket categories.

**Missing-item complaints were substantially hidden under `other`, and the problem was strongly concentrated in two dark stores: DarkStore_007 in Zone D and DarkStore_013 in Zone G.**

The rule-based NLP approach was transparent, reproducible and sufficient to surface this pattern, but its limited ability to recognise unseen wording means the estimated complaint volume should be treated as directional.

The key analytical lesson is:

> **Structured categories told us that customers were unhappy. Complaint text helped explain what was actually going wrong.**