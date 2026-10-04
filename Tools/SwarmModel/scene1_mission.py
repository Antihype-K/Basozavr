"""
Полная миссия сцены 1 по этапам (копия логики SwarmScriptedFlight): раскачка, натяжение и скорость касания на каждом этапе.

    python scene1_mission.py

Этапы: 1 «Натяжение тросов», 2 «Подъём груза», 3 «Перенос груза», 4 «Выгрузка» (до отцепки).
Параметры маршрута и профиля задаются в BASE (cruise, climb, accel, vacc, shift_k).
"""
from swarm_model import run, scene1_route
import numpy as np
BASE=dict(n=6,M=12.0,radius=1.414,L=2.0,Fmax=250.0,kp=40,ki=12,kd=14,shaper='none',smooth=True,T=160,
          cruise=4.0,climb=1.5,accel=1.0,shift_k=0.0,route=scene1_route())
def mission(P, wind=0, gust=0, seeds=(1,)):
    r=[]
    for sd in seeds:
        a,p=run(dict(BASE,**P,wind=wind,gust=gust,seed=sd)); t=a['stage']
        st=[a['swing'][a['stage']==i].max() if (a['stage']==i).any() else 0 for i in range(4)]
        r.append(st+[a['swing'].max(), a['t'][-1], a['v'].max(), np.max(a['sum'])])
    return np.mean(r,0)
if __name__=='__main__':
    print("%-34s | пик °: этапы 1..4 | всего | время до отцепки | v max | Σтяж max"%"конфиг")
    for lab,P in [("сейчас: a1.0 damp.15",dict(shift_k=.15)),("применено: a0.5 damp0",dict(accel=.5)),
                  ("a0.5 + рывок 0.5",dict(accel=.5,jerk=.5)),("a0.5 + рывок 1.0",dict(accel=.5,jerk=1.0)),
                  ("a0.5 + vacc 0.5",dict(accel=.5,vacc=.5)),("a0.5 + рывок 1.0 + vacc 0.5",dict(accel=.5,jerk=1.0,vacc=.5)),
                  ("a0.7 + рывок 0.7 + vacc 0.5",dict(accel=.7,jerk=.7,vacc=.5)),("a0.4 + рывок 0.8 + vacc 0.5",dict(accel=.4,jerk=.8,vacc=.5)),
                  ("a0.5 + рывок 1.0, brake .8",dict(accel=.5,jerk=1.0,brake=.8))]:
        r=mission(P); print("%-34s | %4.1f %4.1f %4.1f %4.1f | %5.2f | %17.1f | %5.2f | %6.0f"%((lab,)+tuple(r)))
