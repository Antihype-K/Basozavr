"""
Проверка требований к системе групповой транспортировки на модели роя.

    python requirements_check.py            # полная проверка (~30 с)
    python requirements_check.py --fmax 250 # с другой предельной силой дрона, Н

Требования (аналитика инженерного решения): 4–6 БПЛА, груз 10–20 кг, линейность 400 % / 600 %
при P1 = 3,3 кг, запас тяги 15–25 %, тяговооруженность ≥ 2, ветер до 8–10 м/с, отказ одного БПЛА.
"""
import argparse
import numpy as np
from swarm_model import run

P1, MD = 3.3, 2.5


def flight(**kw):
    a, p = run(kw)
    t = a['t']; move = (t > 12) & (t < p['T'] - 10); end = t > p['T'] - 10
    err = np.hypot(a['px'][end] - p['D'], a['pz'][end])
    return dict(lifted=a['py'][end].mean() > p['H'] - p['L'] - 1.5, err_mean=err.mean(), err_max=err.max(),
                swing=a['swing'][move].max(), swing_end=a['swing'][end].max(),
                uneven=np.mean((a['tmax'][move] - a['tmin'][move]) / np.maximum(a['tmean'][move], 1e-6)) * 100,
                uneven_hover=np.mean((a['tmax'][end] - a['tmin'][end]) / np.maximum(a['tmean'][end], 1e-6)) * 100)


def max_payload(n, fmax):
    m = n * P1
    while True:
        a, p = run(dict(n=n, M=m + 1, Fmax=fmax, T=50, D=30)); end = a['t'] > 42
        if not (a['py'][end].mean() > p['H'] - p['L'] - 1.0 and np.hypot(a['px'][end] - p['D'], a['pz'][end]).max() < 0.5):
            return m + 0.5
        m += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmax", type=float, default=71.0, help="предельная сила дрона maxForce, Н")
    args = ap.parse_args()
    F = args.fmax
    print(f"Дрон {MD} кг, maxForce {F} Н: тяговооруженность {F / (MD * 9.81):.2f}, "
          f"запас тяги сверх P1={P1} кг: {100 * (F / ((MD + P1) * 9.81) - 1):.0f} %\n")
    rows = []
    for n in (4, 6):
        r = flight(n=n, M=n * P1, Fmax=F)
        rows.append((f"{n} БПЛА поднимают {n}00 % P1 ({n * P1:.1f} кг)", "груз в воздухе",
                     "да" if r['lifted'] else "НЕТ", r['lifted']))
        rows.append((f"{n} БПЛА: точность в точке, без ветра", "м (сред/макс)",
                     f"{r['err_mean']:.2f}/{r['err_max']:.2f}", True))
        rows.append((f"{n} БПЛА: неравномерность натяжений в движении / на зависании", "%",
                     f"{r['uneven']:.0f} / {r['uneven_hover']:.0f}", r['uneven'] <= 20 and r['uneven_hover'] <= 5))
        rows.append((f"{n} БПЛА: пик раскачки в движении / на зависании", "°", f"{r['swing']:.1f} / {r['swing_end']:.1f}", True))
        lim = max_payload(n, F)
        rows.append((f"{n} БПЛА: предельный груз", "кг", f"{lim:.0f} (запас {100 * (lim / (n * P1) - 1):.0f} %)",
                     lim >= n * P1 * 1.15))
    for wind, gust in ((8, 2), (10, 3)):
        r = flight(n=6, M=6 * P1, Fmax=F, wind=wind, gust=gust)
        rows.append((f"6 БПЛА, {6 * P1:.1f} кг, ветер {wind} м/с ± {gust}", "точность сред/макс, м",
                     f"{r['err_mean']:.2f}/{r['err_max']:.2f}", r['lifted']))
    for n, m in ((6, 6 * P1), (4, 4 * P1), (4, 3 * P1)):
        r = flight(n=n, M=m, Fmax=F, fail_id=0, fail_t=30)
        rows.append((f"Отказ 1 из {n} БПЛА, груз {m:.1f} кг", "груз удержан", "да" if r['lifted'] else "НЕТ", r['lifted']))
    w = max(len(r[0]) for r in rows)
    for name, unit, val, ok in rows:
        print(f"{'✓' if ok else '✗'} {name:{w}s}  {val:>22s}  {unit}")


if __name__ == "__main__":
    main()
