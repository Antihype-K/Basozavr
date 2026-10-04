"""
Проверка Python-контроллера из rsma-swarm-delivery-system (gitlab.grimdark.ru) на модели роя.

    python python_controller_check.py

Воспроизводит их контур: сцена 6 БПЛА / 12 кг / трос 2 м / R 1,414 м, JerkLimitedTrajectory (v_max 0,8, a_max 1, j_max 2),
anti_sway.py (K 1,5, D 0,5), ПИД префаба Quadrocopter 5/1/1,5. Сравнивает текущую версию с исправлениями из
gitlab-patches/anti_sway_fix.patch и более жёстким ПИД 10/2/12.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../SwarmModel')
from swarm_model import run
import numpy as np

BASE = dict(n=6, M=12.0, radius=1.414, L=2.0, Fmax=250.0, kp=5, ki=1, kd=1.5, shaper='none', smooth=True,
            H=4.5 + 1.61, D=21.5, vmax=0.8, amax=1.0, T=100, jtraj=dict(vmax=.8, amax=1.0, jmax=2.0))


def case(P, wind=0, gust=0, seeds=(1, 2, 3)):
    r = []
    for sd in seeds:
        a, p = run(dict(BASE, seed=sd, wind=wind, gust=gust, **P)); t = a['t']
        e = np.hypot(a['px'] - p['D'], a['pz']); end = t > t[-1] - 8; fl = (t > 16) & (t < 40)
        r.append((a['swing'][t > 12].max(), a['swing'][(t > 16) & (t < 45)].max(), a['ang'][fl].mean(), a['sum'][fl].mean(), e[end].mean()))
    return np.mean(r, 0)


if __name__ == "__main__":
    print("%-50s | пик с старта | пик в полёте | угол тросов | Σтяж | точность" % "вариант")
    for lab, P in [("сейчас: ПИД 5/1/1.5 + anti-sway как в репозитории", dict(aw_k=1.5, aw_d=0.5)),
                   ("исправлен anti-sway (патч)", dict(aw_k=1.5, aw_d=0.5, aw_mode='fixed')),
                   ("ПИД 10/2/12, anti-sway как в репозитории", dict(kp=10, ki=2, kd=12, aw_k=1.5, aw_d=0.5)),
                   ("ПИД 10/2/12 + исправленный anti-sway", dict(kp=10, ki=2, kd=12, aw_k=1.5, aw_d=0.5, aw_mode='fixed')),
                   ("ПИД 10/2/12, anti-sway выкл.", dict(kp=10, ki=2, kd=12))]:
        r = case(P)
        print("%-50s | %10.2f° | %10.2f° | %9.1f° | %3.0f Н | %.2f м" % ((lab,) + tuple(r)))
    print("\nВетер 10 ± 3 м/с:")
    for lab, P in [("сейчас", dict(aw_k=1.5, aw_d=0.5)),
                   ("ПИД 10/2/12 + исправленный anti-sway", dict(kp=10, ki=2, kd=12, aw_k=1.5, aw_d=0.5, aw_mode='fixed'))]:
        r = case(P, wind=10, gust=3, seeds=(1, 2))
        print("  %-44s пик %.2f°, точность в конце %.2f м" % (lab, r[0], r[4]))
