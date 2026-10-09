using System;

namespace RSMA.uDTP.Topics
{
    /// <summary>
    /// Состояние роя во встроенной миссии (SwarmScriptedFlight) для отчетов Python (run.py).
    /// </summary>
    [Serializable]
    public struct SwarmTelemetry
    {
        public long timestamp;
        public float missionTime;       // время миссии по часам симуляции, с
        public float swingAngle;        // отклонение тросов от вертикали (раскачка груза), градусы
        public float totalTension;      // суммарное натяжение тросов, Н
        public float minTension;        // минимальное натяжение одного троса, Н
        public float maxTension;        // максимальное натяжение одного троса, Н
        public float payloadSpeed;      // скорость груза, м/с
        public float traveledDistance;  // пройденный путь, м
        public int laps;                // выполнено рейсов
        public bool payloadAttached;
    }
}
