"""
Численная модель роя: те же формулы, что в Unity (Quadrocopter.cs, RSMACable.cs, RSMASwarmEnvironment.cs).
Шаг 0.01 с, PID по позиции с анти-windup и приоритетом вертикали, сглаживание цели (maxSpeed/maxAcceleration),
тросы-пружины, ветер с порывами (сопротивление Cd·S), отказ дрона. Нужна для быстрой оценки параметров без Unity;
итоговые цифры подтверждаются тестами в Unity (docs/TEST_GUIDE.md).
"""
import numpy as np
G = np.array([0, -9.81, 0]); DT = 0.01; RHO = 1.225

def cm(v, m):
    n = np.linalg.norm(v); return v if n <= m or n == 0 else v*(m/n)

def run(P):
    p = dict(n=6, M=12.0, radius=3.0, L=5.0, md=2.5, Fmax=250.0, kp=10, ki=2, kd=12, Imax=250.0,
             vmax=4.6, amax=0.5, smooth=True, wind=0.0, gust=0.0, wind_dir=(0, 0, 1),
             cdA_drone=0.1, cdA_load=0.17, eq=False, eq_gain=0.02, eq_lim=1.5,
             fail_id=None, fail_t=1e9, T=70.0, H=13.0, D=70.0, seed=1, k=1000, c=35, cmax=250)
    p.update(P); n = p['n']; rng = np.random.default_rng(p['seed'])
    ang = np.arange(n)*2*np.pi/n + (np.pi/4 if n == 4 else 0)
    off = np.stack([p['radius']*np.cos(ang), np.zeros(n), p['radius']*np.sin(ang)], 1)
    pp = np.array([0, .2, 0.]); pv = np.zeros(3)
    dp = pp + off + [0, .2, 0]; dv = np.zeros((n, 3)); I = np.zeros((n, 3))
    sp = dp.mean(0).copy(); spv = np.zeros(3); hoff = np.zeros(n)
    wdir = np.array(p['wind_dir'], float); wdir /= np.linalg.norm(wdir)
    gust_phase = rng.uniform(0, 6.28, 3)
    log = []
    for kk in range(int(p['T']/DT)):
        t = kk*DT
        goal = np.array([0, p['H'], 0]) if t < 12 else np.array([p['D'], p['H'], 0])
        if t < 12: goal = np.array([0, 0.4 + (p['H']-0.4)*min(t, 10)/10, 0])
        if p['smooth']:
            d = goal - sp; dist = np.linalg.norm(d)
            vl = min(p['vmax'], np.sqrt(2*p['amax']*dist))
            vd = d/dist*vl if dist > 1e-6 else 0*d
            spv = spv + cm(vd - spv, p['amax']*DT); st = spv*DT
            sp = goal.copy() if np.linalg.norm(st) >= dist else sp + st
        else: sp = goal
        # ветер с порывами (сумма синусоид)
        g = p['gust']*(0.6*np.sin(0.9*t+gust_phase[0]) + 0.3*np.sin(2.3*t+gust_phase[1]) + 0.1*np.sin(5.1*t+gust_phase[2]))
        W = wdir*(p['wind'] + g)
        F = np.zeros((n, 3)); Fp = np.zeros(3); ten = np.zeros(n)
        alive = np.array([not (p['fail_id'] == i and t >= p['fail_t']) for i in range(n)])
        for i in range(n):
            tgt = sp + off[i] + [0, hoff[i], 0]
            if alive[i]:
                e = tgt - dp[i]; I[i] += e*DT; I[i] = cm(I[i]*p['ki'], p['Imax'])/p['ki']
                f = p['kp']*e + p['ki']*I[i] - p['kd']*dv[i] - G*p['md']
                fy = np.clip(f[1], -p['Fmax'], p['Fmax']); h = np.array([f[0], 0, f[2]])
                f = cm(h, np.sqrt(p['Fmax']**2 - fy**2)) + [0, fy, 0]
                F[i] += f
            F[i] += G*p['md']
            vr = W - dv[i]; F[i] += 0.5*RHO*p['cdA_drone']*np.linalg.norm(vr)*vr
            d = dp[i] - pp; dist = np.linalg.norm(d)
            if dist > p['L']:
                u = d/dist; ft = np.clip(p['k']*(dist-p['L']) + p['c']*np.dot(dv[i]-pv, u), 0, p['cmax'])
                ten[i] = ft; F[i] -= u*ft; Fp += u*ft
        if p['eq'] and t > 12:   # выравнивание натяжений: перегруженный дрон опускается, недогруженный поднимается
            live = ten[alive]; mean = live.mean() if len(live) else 0
            if mean > 1:
                hoff[alive] -= p['eq_gain']*(ten[alive]-mean)*DT
                hoff = np.clip(hoff, -p['eq_lim'], p['eq_lim'])
        vr = W - pv; Fp += 0.5*RHO*p['cdA_load']*np.linalg.norm(vr)*vr + G*p['M']
        dv = (dv + F/p['md']*DT)/(1+0.8*DT); dp += dv*DT
        pv = (pv + Fp/p['M']*DT)/(1+0.2*DT); pp += pv*DT
        if pp[1] < .2: pp[1] = .2; pv[1] = max(pv[1], 0); pv[[0, 2]] *= .9
        for i in range(n):
            if dp[i, 1] < .1: dp[i, 1] = .1; dv[i] = np.maximum(dv[i]*[0, 1, 0], 0)
        cen = dp[alive].mean(0); r = cen - pp
        sw = np.degrees(np.arccos(np.clip(r[1]/np.linalg.norm(r), -1, 1)))
        lt = ten[alive]
        log.append(dict(t=t, px=pp[0], py=pp[1], pz=pp[2], v=np.linalg.norm(pv), sum=ten.sum(),
                        tmin=lt.min(), tmax=lt.max(), tmean=lt.mean(), swing=sw,
                        ang=np.degrees(np.arccos(np.clip(np.mean([(dp[i,1]-pp[1])/max(np.linalg.norm(dp[i]-pp),1e-6) for i in range(n) if alive[i]]),-1,1)))))
    return {k: np.array([r[k] for r in log]) for k in log[0]}, p

def report(name, a, p):
    t = a['t']; cr = (t > 25) & (t < 40)                 # крейсер
    end = t > p['T'] - 10                                # зависание над точкой
    err = np.hypot(a['px'][end]-p['D'], a['pz'][end])
    unev = (a['tmax'][cr]-a['tmin'][cr])/np.maximum(a['tmean'][cr], 1e-6)*100
    lift_ok = a['py'][end].mean() > p['H'] - p['L'] - 1.5
    print(f"{name:40s} груз в воздухе {'да ' if lift_ok else 'НЕТ'} h={a['py'][end].mean():5.2f}  "
          f"точность {err.mean():.2f}/{err.max():.2f} м  раскачка крейс {a['swing'][cr].max():4.1f}° "
          f"зависание {a['swing'][end].max():4.1f}°  неравномерн. {unev.mean():4.0f}%  угол тросов {a['ang'][cr].mean():4.1f}°")
