#!/usr/bin/env python3
"""Validation of the model's building ignition probability against the by-eye damage review.

Usage: python validate_damage.py   (after the answers are saved in damage/review_answers/labels/*.json and labels2/*.json)
Observed: reviewer labels for every footprint in the MTBS perimeter - batch 1 (590 buildings, damage/review_sample.csv)
plus batch 2 (the other 1,024, damage/review_sample2.csv). Outcome = destroyed or damaged (1) vs survived (0); 'new'
(not built in 2016) and 'unsure' are left out. A second outcome, destroyed only, is reported as a check.
This is a full census, so every building has weight 1 (the weighted formulas below reduce to the plain ones).
Repeat check: batch 2 also showed 60 batch-1 buildings again, blind (keys r<id>); their second label is compared with
the first (agreement, Cohen's kappa) and is not used in the validation.
Model: building_probability/building_probability.csv (50 runs, ms_st09), joined by the 30 m cell holding the
footprint centroid. Buildings in cells the model has no building cell for are counted and left out.
Writes damage/validation/{validation_buildings.csv, validation_summary.txt, validation.png}.
"""
import os, json, glob
import numpy as np
from osgeo import gdal, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "damage/validation"; os.makedirs(OUT, exist_ok=True)
L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); gt = L.GetGeoTransform()
srs = osr.SpatialReference(wkt=L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(wgs, srs)



def read_labels(d):
    return {os.path.basename(f)[:-5]: json.load(open(f))["label"] for f in glob.glob("damage/review_answers/%s/*.json" % d)}


L1, L2 = read_labels("labels"), read_labels("labels2")
lab = {int(k[1:]): v for k, v in L1.items()}
lab.update({int(k[1:]): v for k, v in L2.items() if k[0] == "b"})
rep = [(int(k[1:]), L1["b" + k[1:]], v) for k, v in L2.items() if k[0] == "r"]
auto = {}
for l in list(open("damage/damage_auto.csv"))[1:]:
    r = l.strip().split(","); auto[int(r[0])] = (float(r[1]), float(r[2]), r[-1])
samp = [(k, v[2]) for k, v in sorted(auto.items())]
missing = [k for k, _ in samp if k not in lab]
assert not missing, "buildings without a review label: %s" % missing[:10]
wt = 1.0

# repeat agreement and Cohen's kappa (labels survived/damaged/destroyed/new/unsure)
cats = ["survived", "damaged", "destroyed", "new", "unsure"]
agree = np.mean([a == b for _, a, b in rep])
pa = np.array([[sum(a == c for _, a, _ in rep) for c in cats], [sum(b == c for _, _, b in rep) for c in cats]]) / len(rep)
kappa = (agree - (pa[0] * pa[1]).sum()) / (1 - (pa[0] * pa[1]).sum())
# burned (destroyed or damaged) vs survived, only pairs where both labels are one of these
bb = [(a != "survived", b != "survived") for _, a, b in rep if a in cats[:3] and b in cats[:3]]
agree_b = np.mean([a == b for a, b in bb]) if bb else np.nan

hdr = open("building_probability/building_probability.csv").readline().strip().split(",")
P = np.genfromtxt("building_probability/building_probability.csv", delimiter=",", skip_header=1)
cell = {(int(r[0]), int(r[1])): r for r in P}
FACT = hdr[6:]

rows = []; nocell = 0
for k, g in samp:
    lo, la, _ = auto[k]; h = lab.get(k)
    x, y, _ = tr.TransformPoint(lo, la)
    c = (int((y - gt[3]) / gt[5]), int((x - gt[0]) / gt[1]))
    m = cell.get(c)
    if m is None:
        nocell += 1
    rows.append((k, g, h, wt, c, m))

use = [r for r in rows if r[2] in ("survived", "damaged", "destroyed") and r[5] is not None]
y = np.array([r[2] != "survived" for r in use], float)
ydes = np.array([r[2] == "destroyed" for r in use], float)
w = np.array([r[3] for r in use]); p = np.array([r[5][3] for r in use])
X = np.array([r[5][6:] for r in use])
exposed = np.array([r[5][4] for r in use])


def wauc(score, yy, ww):
    """Weighted AUC = P(score of a burned building > score of a survived one), ties count half."""
    pos, neg = yy == 1, yy == 0
    sp, wp, sn, wn = score[pos], ww[pos], score[neg], ww[neg]
    o = np.argsort(sn); sn, wn = sn[o], wn[o]; cw = np.r_[0, np.cumsum(wn)]
    lo = np.searchsorted(sn, sp, "left"); hi = np.searchsorted(sn, sp, "right")
    return ((cw[lo] + 0.5 * (cw[hi] - cw[lo])) * wp).sum() / (wp.sum() * wn.sum())


def boot_auc(score, yy, ww, n=2000):
    rng = np.random.default_rng(1); a = []
    for _ in range(n):
        i = rng.integers(0, len(yy), len(yy)); a.append(wauc(score[i], yy[i], ww[i]))
    return np.percentile(a, [2.5, 97.5])


def logit(Xs, yy, ww):
    Xd = np.c_[np.ones(len(yy)), Xs]; b = np.zeros(Xd.shape[1])
    for _ in range(50):
        mu = 1 / (1 + np.exp(-Xd @ b)); W = ww * mu * (1 - mu) + 1e-9
        b = b + np.linalg.solve(Xd.T @ (W[:, None] * Xd), Xd.T @ (ww * (yy - mu)))
    mu = 1 / (1 + np.exp(-Xd @ b)); W = ww * mu * (1 - mu)
    se = np.sqrt(np.diag(np.linalg.inv(Xd.T @ (W[:, None] * Xd))))
    return b, se


auc, auc_d = wauc(p, y, w), wauc(p, ydes, w)
ci = boot_auc(p, y, w)
brier = (w * (p - y) ** 2).sum() / w.sum(); base = (w * y).sum() / w.sum()
brier0 = base * (1 - base)
bins = [0, 0.001, 0.2, 0.4, 0.6, 0.8, 0.999, 1.0001]; rel = []
for a, b in zip(bins[:-1], bins[1:]):
    s = (p >= a) & (p < b)
    if s.sum():
        rel.append((a, b, s.sum(), (w[s] * p[s]).sum() / w[s].sum(), (w[s] * y[s]).sum() / w[s].sum()))

Z = (X - (w[:, None] * X).sum(0) / w.sum()) / X.std(0)
bo, so = logit(Z, y, w * len(w) / w.sum())   # weights scaled to mean 1 so the standard errors use the sample size
# model regression rows are in the same factor order; columns: factor,mean,sd,coef,se,OR,OR_low,OR_high,z
reg_rows = [l.strip().split(",") for l in list(open("building_probability/regression.csv"))[1:]]
reg_model = {fn: [r[0]] + r[5:8] for fn, r in zip(FACT, reg_rows)}

# population totals , all reviewed labels incl. those without a model cell
tot = {}
for r in rows:
    tot[r[2]] = tot.get(r[2], 0) + r[3]
# buildings lost where the model never brought fire next to them
lost_unexposed = ((y == 1) & (exposed == 0)); lost_p0 = ((y == 1) & (p == 0))

with open(OUT + "/validation_buildings.csv", "w") as f:
    f.write("id,label_auto,label_review,weight,row,col,p_ignite,runs_exposed\n")
    for k, g, h, ww, c, m in rows:
        f.write("%d,%s,%s,%.3f,%d,%d,%s,%s\n" % (k, g, h, ww, c[0], c[1],
                "" if m is None else "%.3f" % m[3], "" if m is None else "%d" % m[4]))

L_ = []
L_.append("Validation of model building ignition (ms_st09, 50 runs) against the by-eye review (all %d footprints in the MTBS perimeter)" % len(samp))
L_.append("reviewed: %s" % {k: sum(1 for r in rows if r[2] == k) for k in ("survived", "damaged", "destroyed", "new", "unsure")})
L_.append("buildings without a model building cell (left out): %d" % nocell)
L_.append("used: %d buildings (%d burned = destroyed or damaged, %d survived)" % (len(y), y.sum(), (1 - y).sum()))
L_.append("")
L_.append("Repeat check (%d batch-1 buildings shown again blind in batch 2):" % len(rep))
L_.append("  same label %d of %d (%.0f %%), Cohen's kappa %.2f" % (round(agree * len(rep)), len(rep), 100 * agree, kappa))
L_.append("  burned vs survived, pairs with both labels in survived/damaged/destroyed: %d of %d agree (%.0f %%)" %
          (round(agree_b * len(bb)), len(bb), 100 * agree_b))
for (a, b) in sorted(set((a, b) for _, a, b in rep if a != b)):
    L_.append("  first %-9s -> second %-9s %d" % (a, b, sum(1 for _, x, z in rep if (x, z) == (a, b))))
L_.append("")
L_.append("Discrimination: weighted AUC of P(ignite) = %.2f [95%% bootstrap %.2f-%.2f]; destroyed only: %.2f" % (auc, ci[0], ci[1], auc_d))
L_.append("Brier score %.3f (always predicting the observed rate %.2f gives %.3f)" % (brier, base, brier0))
L_.append("Observed burned share %.2f vs mean model P(ignite) %.2f (weighted)" % (base, (w * p).sum() / w.sum()))
L_.append("")
L_.append("Reliability (weighted):  P bin        n   mean P  observed burned share")
for a, b, n, mp, ob in rel:
    L_.append("                       %.2f-%.2f  %4d   %.2f    %.2f" % (a, min(b, 1), n, mp, ob))
L_.append("")
L_.append("Factors: odds ratio per 1 SD   observed (review)        model (P ignite | exposed, regression.csv)")
for j, fn in enumerate(FACT):
    orv = np.exp(bo[j + 1]); lo_, hi_ = np.exp(bo[j + 1] - 1.96 * so[j + 1]), np.exp(bo[j + 1] + 1.96 * so[j + 1])
    mr = reg_model[fn]
    L_.append("  %-40s %.2f [%.2f-%.2f]       %s [%s-%s]" % (fn, orv, lo_, hi_, mr[1], mr[2], mr[3]))
L_.append("")
L_.append("Burned buildings the model never exposed (no adjacent burning cell in any of 50 runs): %d of %d (weighted %.0f of %.0f)" %
          (lost_unexposed.sum(), y.sum(), w[lost_unexposed].sum(), w[y == 1].sum()))
L_.append("Burned buildings with model P(ignite) = 0: %d (weighted %.0f)" % (lost_p0.sum(), w[lost_p0].sum()))
L_.append("Survived buildings with model P(ignite) = 1: %d of %d" % (((y == 0) & (p >= 0.999)).sum(), (1 - y).sum()))
L_.append("")
L_.append("By neighbour building cells within 150 m (thirds of the used buildings):")
L_.append("  neighbours      n   observed burned share   mean model P(ignite)")
nb = X[:, 1]; q = np.percentile(nb, [33.3, 66.7])
for nm, s in (("low  <%.0f" % q[0], nb < q[0]), ("mid", (nb >= q[0]) & (nb < q[1])), ("high >=%.0f" % q[1], nb >= q[1])):
    L_.append("  %-12s %4d   %.2f                    %.2f" % (nm, s.sum(), (w[s] * y[s]).sum() / w[s].sum(), (w[s] * p[s]).sum() / w[s].sum()))
txt = "\n".join(L_); print(txt); open(OUT + "/validation_summary.txt", "w").write(txt + "\n")

# figure: A reliability, B P(ignite) by observed outcome, C odds ratios observed vs model
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
a = ax[0]
mp = [r[3] for r in rel]; ob = [r[4] for r in rel]; ns = [r[2] for r in rel]
a.plot([0, 1], [0, 1], color="#bbbbbb", lw=1, zorder=0)
a.plot(mp, ob, "-", color="#c2410c", lw=2)
a.scatter(mp, ob, s=[12 + 2.2 * n for n in ns], color="#c2410c", edgecolor="white", linewidth=1.5, zorder=3)
for x_, y_, n in zip(mp, ob, ns):
    a.annotate("n=%d" % n, (x_, y_), xytext=(6, -12), textcoords="offset points", fontsize=8, color="#555555")
a.set_xlim(-0.03, 1.03); a.set_ylim(-0.03, 1.03)
a.set_xlabel("Model probability of ignition (bin mean)"); a.set_ylabel("Observed share destroyed or damaged")
a.set_title("A  Reliability (AUC %.2f)" % auc, loc="left", fontsize=11)
a = ax[1]
cols = {"survived": "#2f7d4f", "burned": "#9b2c2c"}
for i, (nm, s) in enumerate((("survived", y == 0), ("burned", y == 1))):
    hh, ed = np.histogram(p[s], bins=np.linspace(0, 1, 11), weights=w[s])
    a.bar(ed[:-1] + 0.05 + (i - 0.5) * 0.042, hh / hh.sum(), width=0.04, color=cols[nm],
          label="%s (%d)" % ("Survived" if nm == "survived" else "Destroyed or damaged", s.sum()))
a.set_xlabel("Model probability of ignition"); a.set_ylabel("Share of buildings (weighted)")
a.set_title("B  Model probability by observed outcome", loc="left", fontsize=11); a.legend(frameon=False, fontsize=9)
a = ax[2]
names = {"distance_to_vegetation": "Distance to vegetation", "neighbour_building_cells_within_150_m": "Neighbour buildings",
         "separation_between_buildings": "Separation", "building_plan_dimension": "Plan dimension", "slope": "Slope"}
for j, fn in enumerate(FACT):
    orv = np.exp(bo[j + 1]); lo_, hi_ = np.exp(bo[j + 1] - 1.96 * so[j + 1]), np.exp(bo[j + 1] + 1.96 * so[j + 1])
    a.plot([lo_, hi_], [j + 0.15] * 2, color="#9b2c2c", lw=2); a.plot(orv, j + 0.15, "o", color="#9b2c2c", ms=7,
                                                                      label="Observed" if j == 0 else None)
    mr = reg_model.get(fn)
    if mr:
        v = [float(t) for t in mr[1:4]]
        a.plot(v[1:3], [j - 0.15] * 2, color="#56605a", lw=2); a.plot(v[0], j - 0.15, "s", color="#56605a", ms=7,
                                                                       label="Model" if j == 0 else None)
a.axvline(1, color="#bbbbbb", lw=1, zorder=0); a.set_xscale("log")
a.set_xticks([0.3, 0.5, 1, 2]); a.set_xticklabels(["0.3", "0.5", "1", "2"]); a.minorticks_off()
a.set_yticks(range(len(FACT))); a.set_yticklabels([names.get(f, f) for f in FACT])
a.set_xlabel("Odds ratio per 1 SD (log scale)"); a.set_title("C  Site factors: observed vs model", loc="left", fontsize=11)
a.legend(frameon=False, fontsize=9, loc="lower right")
for a in ax:
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT + "/validation.png", dpi=170)
print("wrote", OUT)
