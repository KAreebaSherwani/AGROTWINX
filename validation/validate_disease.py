# validation/validate_disease.py
"""
AgroTwinX — Disease Detection Validation Harness
Scores your EXISTING Gemini detector (src/models/disease_detector.py) on a
labeled test set and produces accuracy + a confusion matrix + per-class
precision/recall. Nothing is trained; we measure what you already built.

RUN:
    python validation/validate_disease.py                              # real Gemini
    python validation/validate_disease.py --mock                       # no API (test plumbing)
    python validation/validate_disease.py --limit-per-class 15 --delay 7 --retries 1

OUTPUTS (in validation/results/):
    confusion_matrix.png, confusion_matrix.csv, per_class_report.csv, summary.txt
"""

import os, sys, csv, time, argparse, random
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score

TEST_DIR = Path(__file__).parent / "disease_test_set"
OUT_DIR  = Path(__file__).parent / "results"

# Crop each class belongs to (so we pass the right crop_type to the detector)
CLASS_CROP = {
    # rice
    "healthy": "rice", "rice_healthy": "rice", "rice_blast": "rice", "brown_spot": "rice",
    "bacterial_blight": "rice", "tungro": "rice",
    # wheat
    "leaf_rust": "wheat", "yellow_rust": "wheat", "stem_rust": "wheat",
    "septoria": "wheat", "powdery_mildew": "wheat", "loose_smut": "wheat",
    "wheat_healthy": "wheat",
}

# Map Gemini's free-text disease names -> your canonical class labels.
ALIASES = {
    "rice_blast":       ["blast", "pyricularia", "magnaporthe"],
    "brown_spot":       ["brown spot", "bipolaris", "cochliobolus", "helminthosporium"],
    "bacterial_blight": ["bacterial blight", "xanthomonas", "bacterial leaf"],
    "tungro":           ["tungro"],
    "leaf_rust":        ["leaf rust", "brown rust", "puccinia triticina"],
    "yellow_rust":      ["yellow rust", "stripe rust", "puccinia striiformis"],
    "stem_rust":        ["stem rust", "black rust", "puccinia graminis"],
    "septoria":         ["septoria", "leaf blotch", "septoria tritici"],
    "powdery_mildew":   ["powdery mildew", "blumeria", "erysiphe", "mildew"],
    "loose_smut":       ["loose smut", "smut", "ustilago"],
    "healthy":          ["healthy", "no disease", "normal"],
}

HEALTHY_ALIASES = {"healthy", "rice_healthy", "wheat_healthy"}

def canon(label):
    """Collapse crop-specific healthy folders into one 'healthy' class for scoring."""
    return "healthy" if label in HEALTHY_ALIASES else label

def normalize_label(disease_detected, name_text, valid_labels):
    """Turn the detector's output into one of the known class labels."""
    if not disease_detected:
        return "healthy"
    t = (name_text or "").strip().lower()
    if not t:
        return "healthy"
    for label in valid_labels:
        for kw in ALIASES.get(label, []):
            if kw in t:
                return label
    return "unknown"   # detector named something outside our class set

def collect_test_set():
    samples = []
    if not TEST_DIR.exists():
        return samples
    for class_dir in sorted(TEST_DIR.iterdir()):
        if not class_dir.is_dir():
            continue
        label = class_dir.name
        for img in class_dir.glob("*"):
            if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                samples.append((str(img), label))
    return samples

def predict_real(detector, image_path, crop_type, valid_labels):
    res = detector.detect_from_image(image_path, crop_type=crop_type)
    return normalize_label(res.get("disease_detected", False),
                           res.get("disease_name_english", ""), valid_labels)

def predict_mock(true_label, valid_labels, acc=0.85):
    """Realistic fake: correct ~acc of the time, else a *plausible* confusion."""
    confusions = {
        "rice_blast": "brown_spot", "brown_spot": "rice_blast",
        "leaf_rust": "yellow_rust", "yellow_rust": "leaf_rust",
        "bacterial_blight": "brown_spot", "healthy": "brown_spot",
    }
    if random.random() < acc:
        return true_label
    return confusions.get(true_label, random.choice(valid_labels))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="no API calls; simulate predictions")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between Gemini calls")
    ap.add_argument("--retries", type=int, default=1, help="retries per image on error")
    ap.add_argument("--limit-per-class", type=int, default=0, help="cap images per class (0 = all)")
    ap.add_argument("--quota-wait", type=float, default=60.0, help="seconds to wait on a quota/429 error")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = collect_test_set()
    if args.limit_per_class and not args.mock or (args.limit_per_class and args.mock):
        capped, seen = [], {}
        for path, lab in samples:
            seen[lab] = seen.get(lab, 0)
            if seen[lab] < args.limit_per_class:
                capped.append((path, lab)); seen[lab]+=1
        samples = capped
    if not samples:
        print(f"❌ No images found under {TEST_DIR}")
        print("   Create class folders (healthy/, rice_blast/, ...) and add images.")
        sys.exit(1)

    valid_labels = sorted({lbl for _, lbl in samples} | {"healthy"})
    print(f"📂 {len(samples)} images across {len(valid_labels)} classes: {valid_labels}")
    print(f"🔧 Mode: {'MOCK (no API)' if args.mock else 'REAL Gemini'}\n")

    detector = None
    if not args.mock:
        from src.models.disease_detector import DiseaseDetector
        detector = DiseaseDetector(db=None)

    y_true, y_pred = [], []
    skipped = 0
    random.seed(42)
    for i, (path, true_label) in enumerate(samples, 1):
        crop = CLASS_CROP.get(true_label, "rice")
        pred = None
        if args.mock:
            pred = predict_mock(true_label, valid_labels)
        else:
            failed = False
            for attempt in range(args.retries + 1):
                try:
                    pred = predict_real(detector, path, crop, valid_labels)
                    failed = False
                    break
                except Exception as e:
                    msg = str(e).lower()
                    failed = True
                    if "quota" in msg or "429" in msg or "rate" in msg or "exceeded" in msg:
                        print(f"   ⏳ quota hit on {Path(path).name}; waiting {args.quota_wait:.0f}s ...")
                        time.sleep(args.quota_wait)
                    elif "high demand" in msg or "overloaded" in msg or "unavailable" in msg:
                        print(f"   ⚠️  transient error on {Path(path).name}; retrying ...")
                        time.sleep(args.delay * (attempt + 1))
                    else:
                        print(f"   ⚠️  {Path(path).name} attempt {attempt+1} failed: {e}")
                        time.sleep(args.delay * (attempt + 1))
            time.sleep(args.delay)  # free-tier rate-limit guard
            if failed and pred is None:
                # API never returned -> SKIP (do not score as a misdiagnosis)
                skipped += 1
                print(f"  [{i}/{len(samples)}] ⏭️  {true_label:18s} -> SKIPPED (API/quota error)")
                continue
        ct, cp = canon(true_label), canon(pred)
        y_true.append(ct); y_pred.append(cp)
        mark = "✅" if cp == ct else "❌"
        print(f"  [{i}/{len(samples)}] {mark} {true_label:18s} -> {pred}")

    labels = sorted(set(y_true) | set(y_pred))
    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0, output_dict=True)

    # ---- confusion matrix PNG ----
    fig, ax = plt.subplots(figsize=(8, 6.5))
    im = ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right"); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted (Gemini)"); ax.set_ylabel("Actual (ground truth)")
    ax.set_title(f"AgroTwinX Disease Detection — Confusion Matrix\nAccuracy = {acc*100:.1f}%  (n={len(samples)})")
    thr = cm.max() / 2 if cm.max() else 0.5
    for r in range(len(labels)):
        for c in range(len(labels)):
            ax.text(c, r, cm[r, c], ha="center", va="center",
                    color="white" if cm[r, c] > thr else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "confusion_matrix.png", dpi=150)

    # ---- CSVs ----
    with open(OUT_DIR / "confusion_matrix.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["actual\\predicted"] + labels)
        for r, lab in enumerate(labels): w.writerow([lab] + list(cm[r]))
    with open(OUT_DIR / "per_class_report.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["class", "precision", "recall", "f1", "support"])
        for lab in labels:
            d = report.get(lab, {})
            w.writerow([lab, f"{d.get('precision',0):.3f}", f"{d.get('recall',0):.3f}",
                        f"{d.get('f1-score',0):.3f}", int(d.get('support',0))])

    # ---- summary ----
    lines = [
        "AgroTwinX — Disease Detection Validation",
        "="*48,
        f"Mode: {'MOCK' if args.mock else 'REAL Gemini'}",
        f"Images tested : {len(y_true)} (scored)  |  skipped (API errors): {skipped}",
        f"Classes       : {labels}",
        f"OVERALL ACCURACY: {acc*100:.1f}%",
        f"Macro F1        : {report['macro avg']['f1-score']:.3f}",
        "",
        "Per-class (precision / recall / f1):",
    ]
    for lab in labels:
        d = report.get(lab, {})
        lines.append(f"  {lab:18s} {d.get('precision',0):.2f} / {d.get('recall',0):.2f} / {d.get('f1-score',0):.2f}")
    summary = "\n".join(lines)
    (OUT_DIR / "summary.txt").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    print(f"\n📁 Saved to {OUT_DIR}/  (confusion_matrix.png, .csv, per_class_report.csv, summary.txt)")

if __name__ == "__main__":
    main()