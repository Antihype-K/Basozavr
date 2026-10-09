using System;
using Newtonsoft.Json.Linq;
using UnityEngine;

/// <summary>
/// Параметры миссии, заданные из Python (Python/run.py): скорость, высота, точки маршрута,
/// число дронов, масса груза, ветер и т.д.
///
/// JSON: {"delivery": {поля SwarmDeliveryScene}, "environment": {поля RSMASwarmEnvironment}}.
/// Передается переменной окружения RSMA_MISSION_CONFIG процесса Unity: ее задают
/// автозапуск (Python), редактор по запросу Python (RSMALauncher) или команда NetMQ
/// SetMissionConfig. Переменная переживает перезагрузку домена при входе в Play.
/// </summary>
public static class MissionConfig
{
    public const string EnvVar = "RSMA_MISSION_CONFIG";

    public static string Json => Environment.GetEnvironmentVariable(EnvVar);

    public static void Set(string json) => Environment.SetEnvironmentVariable(EnvVar, string.IsNullOrWhiteSpace(json) ? null : json);

    public static void Clear() => Environment.SetEnvironmentVariable(EnvVar, null);

    /// <summary>Применяет конфигурацию поверх значений из сцены. Вызывать до сборки роя.</summary>
    public static void Apply(SwarmDeliveryScene scene, RSMASwarmEnvironment environment)
    {
        string json = Json;
        if (string.IsNullOrWhiteSpace(json))
            return;

        try
        {
            JObject root = JObject.Parse(json);
            if (root["delivery"] is JObject delivery && scene != null)
                JsonUtility.FromJsonOverwrite(delivery.ToString(), scene);
            if (root["environment"] is JObject env && environment != null)
                JsonUtility.FromJsonOverwrite(env.ToString(), environment);
            Debug.Log($"[MissionConfig] Параметры из Python: {json}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"[MissionConfig] Не удалось применить параметры: {ex.Message}\n{json}");
        }
    }
}
