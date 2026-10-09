using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Добавляет полёт дрона по скрипту в существующую сцену проекта (Assets/1.unity)
/// и делает её первой в Build Settings.
/// Меню: БАСозавр → Добавить полёт по скрипту в сцену 1.
/// </summary>
public static class BASozavrScriptedFlightInstaller
{
    public const string ScenePath = "Assets/1.unity";
    private const string DronePrefabPath = "Assets/Prefabs/Drones/Quadrocopter.prefab";
    private const string RootName = "ScriptedFlight";

    [MenuItem("БАСозавр/Добавить полёт по скрипту в сцену 1")]
    public static void InstallIntoScene()
    {
        Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

        // Повторный запуск не плодит дубликаты
        foreach (ScriptedFlightScene old in Object.FindObjectsByType<ScriptedFlightScene>(FindObjectsSortMode.None))
        {
            Object.DestroyImmediate(old.gameObject);
        }

        GameObject root = new GameObject(RootName);
        ScriptedFlightScene bootstrap = root.AddComponent<ScriptedFlightScene>();

        GameObject dronePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(DronePrefabPath);
        if (dronePrefab == null) Debug.LogError($"[Installer] Префаб дрона не найден: {DronePrefabPath}");
        bootstrap.dronePrefab = dronePrefab;

        // Координаты задаём по XZ, высоту скрипт сам возьмёт с рельефа
        bootstrap.basePosition = new Vector3(115.0f, 0.0f, 85.0f);
        bootstrap.deliveryPosition = new Vector3(75.0f, 0.0f, 45.0f);
        bootstrap.cruiseHeight = 12.0f;   // выше крон деревьев
        bootstrap.dropHeight = 1.5f;
        bootstrap.unloadTime = 3.0f;
        bootstrap.buildGround = false;    // на сцене есть рельеф
        bootstrap.snapToGround = true;
        bootstrap.loop = true;

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);

        RegisterSceneFirst(ScenePath);

        Debug.Log($"[Installer] Объект '{RootName}' добавлен в {ScenePath}, сцена первая в Build Settings.");
    }

    public static void RegisterSceneFirst(string scenePath)
    {
        List<EditorBuildSettingsScene> scenes = EditorBuildSettings.scenes
            .Where(s => s.path != scenePath)
            .ToList();

        scenes.Insert(0, new EditorBuildSettingsScene(scenePath, true));
        EditorBuildSettings.scenes = scenes.ToArray();
    }

    private const string PayloadPrefabPath = "Assets/Prefabs/Drones/Payload.prefab";
    private const string SwarmRootName = "SwarmDelivery";

    /// <summary>
    /// Ставит в сцену 1 доставку груза роем. Одиночный полёт из сцены убирается,
    /// иначе в кадре окажутся и рой, и отдельный дрон.
    /// </summary>
    [MenuItem("БАСозавр/Добавить полёт роя с грузом в сцену 1")]
    public static void InstallSwarmIntoScene()
    {
        Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

        foreach (ScriptedFlightScene single in Object.FindObjectsByType<ScriptedFlightScene>(FindObjectsSortMode.None))
        {
            Object.DestroyImmediate(single.gameObject);
        }
        foreach (SwarmDeliveryScene old in Object.FindObjectsByType<SwarmDeliveryScene>(FindObjectsSortMode.None))
        {
            Object.DestroyImmediate(old.gameObject);
        }
        foreach (RSMASwarmEnvironment old in Object.FindObjectsByType<RSMASwarmEnvironment>(FindObjectsSortMode.None))
        {
            Object.DestroyImmediate(old.gameObject);
        }

        GameObject root = new GameObject(SwarmRootName);

        RSMASwarmEnvironment env = root.AddComponent<RSMASwarmEnvironment>();
        env.dronePrefab = LoadPrefab(DronePrefabPath);
        env.payloadPrefab = LoadPrefab(PayloadPrefabPath);
        env.numDrones = 6;
        env.payloadMass = 12.0f;   // середина диапазона ТЗ 10-20 кг
        env.radius = 1.414f;
        env.cableLength = 2.0f;
        env.buildOnStart = false;  // сборкой управляет SwarmDeliveryScene

        SwarmDeliveryScene mission = root.AddComponent<SwarmDeliveryScene>();
        mission.basePosition = new Vector3(115.0f, 0.0f, 85.0f);
        mission.deliveryPosition = new Vector3(75.0f, 0.0f, 45.0f);
        mission.cruiseHeight = 12.0f;
        mission.dropHeight = 0.55f;
        mission.unloadTime = 3.0f;
        mission.loop = true;

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);

        RegisterSceneFirst(ScenePath);

        Debug.Log($"[Installer] Объект '{SwarmRootName}' добавлен в {ScenePath}: " +
                  $"{env.numDrones} БПЛА, груз {env.payloadMass} кг на тросах {env.cableLength} м.");
    }

    private static GameObject LoadPrefab(string path)
    {
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null) Debug.LogError($"[Installer] Префаб не найден: {path}");
        return prefab;
    }

    /// <summary>Сборка Linux-плеера сцены 1 для headless-проверки полёта.</summary>
    public static void BuildLinuxPlayer()
    {
        BuildPlayerOptions options = new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = "Builds/Scene1Flight/Scene1Flight.x86_64",
            target = BuildTarget.StandaloneLinux64,
            options = BuildOptions.Development
        };

        var report = BuildPipeline.BuildPlayer(options);
        Debug.Log($"[Installer] Сборка плеера: {report.summary.result}, {report.summary.totalSize} байт.");
    }

    /// <summary>Установка роя и сборка плеера одним вызовом — для запуска из CLI.</summary>
    public static void InstallSwarmAndBuild()
    {
        InstallSwarmIntoScene();

        BuildPlayerOptions options = new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = "Builds/SwarmDelivery/SwarmDelivery.x86_64",
            target = BuildTarget.StandaloneLinux64,
            options = BuildOptions.Development
        };

        var report = BuildPipeline.BuildPlayer(options);
        Debug.Log($"[Installer] Сборка плеера роя: {report.summary.result}, {report.summary.totalSize} байт.");

        if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            EditorApplication.Exit(1);
        }
    }
}
