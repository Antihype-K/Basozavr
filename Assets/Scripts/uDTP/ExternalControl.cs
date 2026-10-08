using System.Collections.Generic;
using RSMA.uDTP.Topics;
using UnityEngine;

namespace RSMA.uDTP
{
    /// <summary>
    /// Разделение управления между Unity-контроллерами и внешними скриптами (Python).
    ///
    /// Пока клиент продлевает аренду в топике ExternalControl_{robot}, встроенные
    /// контроллеры этого робота не публикуют свои команды и не перетирают команды скрипта.
    /// Если скрипт остановился или упал, аренда истекает и управление возвращается Unity.
    /// Время истечения считается по часам Unity с момента последнего изменения timestamp,
    /// поэтому расхождение часов между машинами не важно.
    /// </summary>
    public static class ExternalControl
    {
        public const int None = 0;
        /// <summary>Скрипт задает скорость/цель, низкоуровневые контроллеры (MotionController) работают.</summary>
        public const int Commands = 1;
        /// <summary>Скрипт управляет приводами напрямую, отключаются и низкоуровневые контроллеры.</summary>
        public const int Actuators = 2;

        private static readonly Dictionary<string, (long timestamp, float seenAt)> _seen =
            new Dictionary<string, (long, float)>();

        public static string TopicName(string robot) => $"ExternalControl_{robot}";

        /// <summary>Текущий уровень внешнего управления роботом (0, если аренды нет или она истекла).</summary>
        public static int Level(string robot)
        {
            var lease = DataBroker.GetState<ControlLease>(TopicName(robot));
            if (lease.level <= None || lease.timestamp == 0)
                return None;

            float now = Time.realtimeSinceStartup;
            if (!_seen.TryGetValue(robot, out var seen) || seen.timestamp != lease.timestamp)
            {
                seen = (lease.timestamp, now);
                _seen[robot] = seen;
            }

            float duration = lease.duration > 0 ? lease.duration : 0.5f;
            return now - seen.seenAt <= duration ? lease.level : None;
        }

        /// <summary>True, если скрипт управляет роботом на уровне не ниже level.</summary>
        public static bool IsActive(string robot, int level = Commands) => Level(robot) >= level;
    }
}
