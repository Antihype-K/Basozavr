"""
Раскачка груза на сцене Assets/1.unity (SwarmDeliveryScene): калибровка модели по видео и перебор параметров.

    python scene1_swing.py

Геометрия сцены: 6 БПЛА, груз 12 кг, трос 2 м, радиус строя 1,414 м, тяга 250 Н, ПИД 40/12/14, плечо 56,6 м.
Калибровка: модель даёт суммарное натяжение 164 Н (видео 159–164), на трос 22–32 Н (видео 21–33),
максимальную скорость 4,65 м/с (видео 4,6) при ускорении 1,0 и swingDamping 0,15 (значения до оптимизации).
"""
from swarm_model import run
import numpy as np
S1=dict(n=6,M=12.0,radius=1.414,L=2.0,Fmax=250.0,kp=40,ki=12,kd=14,vmax=4.0,amax=1.0,shaper='none',H=13.45,D=56.6,T=90)
def m(P, wind=0, gust=0, seeds=(1,2), D=None):
    out=[]
    for sd in seeds:
        q=dict(S1, **P); 
        if D: q['D']=D
        a,p=run(dict(q,wind=wind,gust=gust,seed=sd)); t=a['t']
        mv=(t>12)&(t<t[-1]-15)
        e=np.hypot(a['px']-p['D'],a['pz']); bad=np.where(e>0.3)[0]; tarr=t[bad[-1]+1] if len(bad) and bad[-1]+1<len(t) else float('nan')
        end=t>t[-1]-8
        out.append((a['swing'][mv].max(), np.sqrt(np.mean(a['swing'][mv]**2)), tarr, e[end].mean(), a['v'].max(), np.mean((a['tmax'][mv]-a['tmin'][mv])/np.maximum(a['tmean'][mv],1e-6))*100))
    return np.mean(out,0)
if __name__=='__main__':
    print("%-34s %7s %6s %9s %8s %7s %7s"%("конфиг (без ветра)","пик °","rms °","дошёл, с","ошибка","v max","неравн%"))
    for lab,P in [("как сейчас: a1.0, damp .15",dict(shift_k=.15)),("a1.0, damp 0",{}),
                  ("a0.7, damp 0",dict(amax=.7)),("a0.5, damp 0",dict(amax=.5)),("a0.4, damp 0",dict(amax=.4)),("a0.3, damp 0",dict(amax=.3)),
                  ("a1.0, ZVD T5",dict(shaper='zvd',shaper_T=5.0)),("a0.7, ZVD T5",dict(amax=.7,shaper='zvd',shaper_T=5.0)),
                  ("a0.5, ZVD T5",dict(amax=.5,shaper='zvd',shaper_T=5.0)),("a0.4, ZVD T5",dict(amax=.4,shaper='zvd',shaper_T=5.0)),
                  ("a0.3, ZVD T5",dict(amax=.3,shaper='zvd',shaper_T=5.0))]:
        r=m(P); print("%-34s %7.2f %6.2f %9.1f %8.3f %7.2f %7.0f"%((lab,)+tuple(r)))
