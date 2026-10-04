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

class Script:
    """
    Копия логики SwarmScriptedFlight (Unity): маршрут в координатах груза, уставка с ограничением скорости и ускорения,
    вертикаль отдельно со скоростью climb, высота строя из условия натянутого троса, выдержки и отцепка.
    Дополнительно (чего нет в C#): vacc — ограничение вертикального ускорения, jerk — ограничение рывка по горизонтали.
    """

    def __init__(self, p, payload_pos):
        self.p = p
        r = min(p['radius'], p['L']*0.85)
        length = p['L']
        for _ in range(6):
            h = np.sqrt(max(0.01, length**2 - r**2))
            tension = p['M']*9.81*length/(p['n']*h)
            length = p['L'] + tension/max(1.0, p['k'])
        self.height = np.sqrt(max(0.01, length**2 - r**2))
        self.sp = payload_pos.copy(); self.hs = 0.0; self.ha = 0.0; self.vs = 0.0
        self.idx = 0; self.holding = False; self.hold = 0.0; self.done = False; self.released = False
        self.route = p['route']

    def step(self, pp, dt):
        p = self.p; wp = self.route[self.idx]; target = wp['pos']
        # горизонталь: трапеция с торможением на подходе
        to = target - self.sp; hor = np.array([to[0], 0, to[2]]); left = np.linalg.norm(hor)
        if left > 1e-4:
            allowed = min(p['cruise'], np.sqrt(2*max(0.01, p['accel'])*left*p.get('brake', 1.0)))
            if p.get('jerk', 0) > 0:
                want_a = np.clip((allowed - self.hs)/dt, -p['accel'], p['accel'])
                self.ha += np.clip(want_a - self.ha, -p['jerk']*dt, p['jerk']*dt)
                self.hs = max(0.0, self.hs + self.ha*dt)
            else:
                self.hs += np.clip(allowed - self.hs, -p['accel']*dt, p['accel']*dt)
            self.sp = self.sp + hor/left*min(self.hs*dt, left)
        else:
            self.hs = 0.0; self.ha = 0.0; self.sp[0], self.sp[2] = target[0], target[2]
        # вертикаль
        dy = target[1] - self.sp[1]
        if p.get('vacc', 0) > 0:
            want = np.sign(dy)*min(p['climb'], np.sqrt(2*p['vacc']*abs(dy)))
            self.vs += np.clip(want - self.vs, -p['vacc']*dt, p['vacc']*dt)
            self.sp[1] += np.clip(self.vs*dt, -abs(dy), abs(dy)) if abs(dy) > 1e-6 else 0
        else:
            self.sp[1] += np.clip(dy, -p['climb']*dt, p['climb']*dt)
        height = wp.get('height') or self.height
        stage = self.idx
        if not self.holding:
            reached = np.linalg.norm(self.sp - target) <= 0.05 and np.linalg.norm(pp - target) <= wp['r']
            if reached:
                self.holding = True; self.hold = wp['hold']
        if self.holding:
            self.hold -= dt
            if self.hold <= 0:
                if wp.get('release'): self.released = True; self.done = True
                self.holding = False; self.hs = 0.0; self.ha = 0.0
                if self.idx + 1 < len(self.route): self.idx += 1
                else: self.done = True
        return self.sp.copy(), height, stage


def scene1_route(D=56.6, cruise_h=12.0, drop_h=0.55, hold=(2.0, 1.5, 1.5, 3.0), ground=0.2):
    """Маршрут SwarmDeliveryScene до выгрузки (координаты груза)."""
    b = np.array([0, ground, 0.0]); d = np.array([D, ground, 0.0])
    return [dict(label='Натяжение тросов', pos=b, hold=hold[0], r=0.6),
            dict(label='Подъём груза', pos=b + [0, cruise_h, 0], hold=hold[1], r=0.5),
            dict(label='Перенос груза', pos=d + [0, cruise_h, 0], hold=hold[2], r=0.8),
            dict(label='Выгрузка', pos=d + [0, drop_h, 0], hold=hold[3], r=0.4, release=True)]


def run(P):
    p = dict(n=6, M=12.0, radius=3.0, L=5.0, md=2.5, Fmax=250.0, kp=10, ki=2, kd=12, Imax=250.0,
             vmax=4.6, amax=0.3, smooth=True, wind=0.0, gust=0.0, wind_dir=(0, 0, 1),
             cdA_drone=0.1, cdA_load=0.17, eq=False, eq_gain=0.02, eq_lim=1.5,
             fail_id=None, shaper='zvd', shaper_T=5.5, shift_k=0.0, shift_lim=1.0,  fail_t=1e9, T=70.0, H=13.0, D=70.0, seed=1, k=1000, c=35, cmax=250)
    p.update(P); n = p['n']; rng = np.random.default_rng(p['seed'])
    ang = np.arange(n)*2*np.pi/n + (np.pi/4 if n == 4 else 0)
    off = np.stack([p['radius']*np.cos(ang), np.zeros(n), p['radius']*np.sin(ang)], 1)
    pp = np.array([0, .2, 0.]); pv = np.zeros(3)
    dp = pp + off + [0, .2, 0]; dv = np.zeros((n, 3)); I = np.zeros((n, 3))
    sp = dp.mean(0).copy(); spv = np.zeros(3); hoff = np.zeros(n)
    wdir = np.array(p['wind_dir'], float); wdir /= np.linalg.norm(wdir)
    gust_phase = rng.uniform(0, 6.28, 3)
    log = []; hist = []
    script = Script(p, pp) if p.get('route') else None
    for kk in range(int(p['T']/DT)):
        t = kk*DT
        if script and script.done: break
        goal = np.array([0, p['H'], 0]) if t < 12 else np.array([p['D'], p['H'], 0])
        if t < 12: goal = np.array([0, 0.4 + (p['H']-0.4)*min(t, 10)/10, 0])
        stage = -1
        if script:
            centre, height, stage = script.step(pp, DT)
            sp = centre + [0, height, 0]
        elif p['smooth']:
            d = goal - sp; dist = np.linalg.norm(d)
            vl = min(p['vmax'], np.sqrt(2*p['amax']*dist))
            vd = d/dist*vl if dist > 1e-6 else 0*d
            spv = spv + cm(vd - spv, p['amax']*DT); st = spv*DT
            sp = goal.copy() if np.linalg.norm(st) >= dist else sp + st
        else: sp = goal
        hist.append(sp.copy())
        spc = sp
        if p['shaper'] != 'none':   # формирователь входа: импульсы с шагом T/2 гасят колебания маятника
            half = int(round(p['shaper_T']/2/DT))
            taps = [(0.5, 0), (0.5, half)] if p['shaper'] == 'zv' else [(0.25, 0), (0.5, half), (0.25, 2*half)]
            spc = sum(w*hist[max(0, len(hist)-1-d)] for w, d in taps)
        # ветер с порывами (сумма синусоид)
        g = p['gust']*(0.6*np.sin(0.9*t+gust_phase[0]) + 0.3*np.sin(2.3*t+gust_phase[1]) + 0.1*np.sin(5.1*t+gust_phase[2]))
        W = wdir*(p['wind'] + g)
        F = np.zeros((n, 3)); Fp = np.zeros(3); ten = np.zeros(n)
        alive = np.array([not (p['fail_id'] == i and t >= p['fail_t']) for i in range(n)])
        # как в SwarmScriptedFlight.swingDamping: строй сдвигается по горизонтальной скорости груза
        shift = cm(p['shift_k']*pv*[1, 0, 1], p['shift_lim']) if p['shift_k'] > 0 else np.zeros(3)
        for i in range(n):
            tgt = spc + off[i] + [0, hoff[i], 0] + shift
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
        log.append(dict(t=t, stage=stage, offx=r[0], offz=r[2], cx=cen[0], px=pp[0], py=pp[1], pz=pp[2], v=np.linalg.norm(pv), sum=ten.sum(),
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
