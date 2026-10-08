using System;

namespace RSMA.uDTP.Topics
{
    /// <summary>
    /// "Аренда" управления роботом внешним клиентом (Python-скриптом).
    /// Клиент публикует ее в топик ExternalControl_{robot} и обновляет timestamp,
    /// пока управляет; см. ExternalControl.
    /// </summary>
    [Serializable]
    public struct ControlLease
    {
        public long timestamp;   // меняется при каждом продлении
        public int level;        // 0 — управление отдано, 1 — команды скорости/цели, 2 — прямое управление приводами
        public float duration;   // через сколько секунд без продления аренда истекает
    }
}
