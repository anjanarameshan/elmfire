#!/usr/bin/env python3
"""Extra damage label versions from the parcel rebuild proxy, and a robustness check of the key vulnerability results.

Usage: python label_versions_parcel.py   (after parcel_damage_proxy.py; reads vulnerability/features.csv,
       features_topo.csv, pairs.csv, parcel_join.csv)
New versions (1 burned, 0 survived, -1 left out), next to A / B / C (see vulnerability_features.py):
  D  parcel proxy: footprint alone on its 2016 parcel (n_fp = 1) and that parcel had a building on 12 Oct 2016;
     main building rebuilt (built 2017+) or gone = 1, same = 0
  G  agreement: A and D both defined and equal (the most trustworthy subset)
  N  A, plus 'new' footprints on rebuilt / gone parcels counted as burned (the 2019 footprint is the rebuilt house,
     a house stood there in 2016)
d_burned_<v> = edge distance to the nearest burned building within 100 m (pairs.csv), else 999.
Writes vulnerability/features_labels.csv (id, y_A..y_N, d_burned_*), vulnerability/label_versions_summary.txt.
"""
import csv
import numpy as np

OUT = "vulnerability"
R = list(csv.DictReader(open(OUT + "/features.csv")))
T = {r["id"]: r for r in csv.DictReader(open(OUT + "/features_topo.csv"))}
J = {r["id"]: r for r in csv.DictReader(open(OUT + "/parcel_join.csv"))}
F = lambda k: np.array([float(r[k]) for r in R])
ids = F("id").astype(int); idx = {k: i for i, k in enumerate(ids)}; N = len(R)
Y = {v: F("y_" + v) for v in "ABC"}
proxy = np.array([J[r["id"]]["proxy"] for r in R]); nfp = np.array([int(J[r["id"]]["n_fp"]) for r in R])
review = np.array([r["review"] for r in R])
gone = np.isin(proxy, ["rebuilt", "gone"])
Y["D"] = np.where((nfp == 1) & gone, 1, np.where((nfp == 1) & (proxy == "same"), 0, -1)).astype(float)
Y["G"] = np.where((Y["A"] >= 0) & (Y["D"] >= 0) & (Y["A"] == Y["D"]), Y["A"], -1)
Y["N"] = np.where((review == "new") & gone, 1, Y["A"])
VERS = "ABCDGN"

P = np.loadtxt(OUT + "/pairs.csv", delimiter=",", skiprows=1)
I = np.array([idx[int(a)] for a in P[:, 0]]); Jj = np.array([idx[int(b)] for b in P[:, 1]]); D = P[:, 2]
DB = {}
for v in VERS:
    d = np.full(N, 999.0)
    for a, b in ((I, Jj), (Jj, I)):           # pairs may be listed one way only
        m = Y[v][b] == 1
        np.minimum.at(d, a[m], D[m])
    DB[v] = d
with open(OUT + "/features_labels.csv", "w") as f:
    w = csv.writer(f); w.writerow(["id"] + ["y_" + v for v in VERS] + ["d_burned_" + v for v in VERS])
    for i in range(N):
        w.writerow([ids[i]] + ["%d" % Y[v][i] for v in VERS] + ["%.2f" % DB[v][i] for v in VERS])


def logit(X, y):
    """Logistic regression by IRLS; returns coefficients and standard errors (X without intercept)."""
    X = np.column_stack([np.ones(len(y)), X]); b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b)); W = p * (1 - p)
        H = X.T @ (X * W[:, None]); step = np.linalg.solve(H, X.T @ (y - p)); b += step
        if np.abs(step).max() < 1e-8:
            break
    return b, np.sqrt(np.diag(np.linalg.inv(H)))


z = lambda a, k: (a - a[k].mean()) / a[k].std()
veg10, veg30, n30 = F("veg15_1.5_10"), F("veg15_10_30"), F("n_30")
slope = np.array([float(T[r["id"]]["slope_deg"]) for r in R]); elev = np.array([float(T[r["id"]]["elevation_m"]) for r in R])
tpi = np.array([float(T[r["id"]]["tpi300_m"]) for r in R])
L = ["Label versions (1 burned / 0 survived; counts) and key results per version",
     "A reviewer | B reviewer = automatic | C upper bound | D parcel proxy (single-footprint parcels) | G A = D | N A + 'new' on rebuilt parcels", ""]
L.append("ver   n     burned  share   OR veg 1.5-10  OR veg 10-30  OR n_30   OR slope   OR elev   OR TPI300  | burned share by slope 0-5/5-15/15-25/>25 deg | no burned <40 m")
for v in VERS:
    k = Y[v] >= 0; y = Y[v][k]
    X = np.column_stack([z(a, k)[k] for a in (veg10, veg30, n30, slope, elev, tpi)])
    b, se = logit(X, y)
    ors = " ".join("%5.2f [%4.2f-%4.2f]" % (np.exp(b[j]), np.exp(b[j] - 1.96 * se[j]), np.exp(b[j] + 1.96 * se[j])) for j in range(1, 7))
    sh = "/".join("%.2f" % Y[v][k & (slope >= lo) & (slope < hi)].mean() for lo, hi in ((0, 5), (5, 15), (15, 25), (25, 90)))
    iso = np.mean(DB[v][k & (Y[v] == 1)] > 40)
    L.append("%s  %5d  %5d   %.2f   %s  | %s | %.0f%%" % (v, k.sum(), int(y.sum()), y.mean(), ors, sh, 100 * iso))
k = (Y["A"] >= 0) & (Y["D"] >= 0); a, d = Y["A"][k], Y["D"][k]
po = np.mean(a == d); pe = a.mean() * d.mean() + (1 - a.mean()) * (1 - d.mean())
L += ["", "OR = odds ratio per 1 SD, all six terms in one logistic model (vegetation, density, slope, elevation, TPI 300 m).",
      "Agreement A vs D (both defined): %d buildings, %.0f%% agree; kappa %.2f" % (k.sum(), 100 * po, (po - pe) / (1 - pe)),
      "'new' footprints: %d; on rebuilt / gone parcels %d (-> burned in N); on unchanged parcels %d" % (
          (review == "new").sum(), ((review == "new") & gone).sum(), ((review == "new") & (proxy == "same")).sum())]
txt = "\n".join(L); print(txt); open(OUT + "/label_versions_summary.txt", "w").write(txt + "\n")
