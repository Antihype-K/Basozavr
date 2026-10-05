using System;
using UnityEngine;

namespace RSMA.uDTP.Topics
{
    /// <summary>Статус миссии, который публикует внешний (Python) контроллер для отображения в RSMA.</summary>
    [Serializable]
    public struct MissionStatus
    {
        public long timestamp;
        // LIFT, TRAJECTORY, HOVER, LAND, LAND_DRONES, FINISHED
        public string phase;
        // Доля пути до точки доставки, 0..1
        public float progress;
        public float distanceToFinish;
        // Уставка положения груза (координаты Unity)
        public Vector3 setpoint;
        public Vector3 finish;
    }
}
