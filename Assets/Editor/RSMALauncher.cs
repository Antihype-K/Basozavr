using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Запуск сцены по команде из Python (Python/run.py, scene.launcher):
///
/// 1. Unity закрыта — Python запускает редактор:
///      Unity -projectPath &lt;проект&gt; -executeMethod RSMALauncher.PlayScene -rsmaScene Assets/1.unity
///    параметры миссии — в переменной окружения RSMA_MISSION_CONFIG (см. MissionConfig.cs).
/// 2. Unity открыта, но не в Play — Python кладет запрос в Temp/rsma_play_request.json:
///      {"scene": "Assets/1.unity", "config": "{...}"}
///    редактор (этот класс) открывает сцену с параметрами и нажимает Play.
/// 3. Unity в Play — Python меняет параметры и сцену командами NetMQ (SetMissionConfig, LoadScene).
///
/// После выхода из Play параметры из Python и стартовая сцена Play сбрасываются.
/// </summary>
[InitializeOnLoad]
public static class RSMALauncher
{
    public const string DefaultScene = "Assets/1.unity";
    public const string RequestFile = "Temp/rsma_play_request.json";
    private const string StartSceneSetKey = "RSMALauncher.StartSceneSet";

    private static double nextCheck;

    [Serializable]
    private class PlayRequest
    {
        public string scene;
        public string config;
    }

    static RSMALauncher()
    {
        EditorApplication.update += WatchRequests;
        EditorApplication.playModeStateChanged += OnPlayModeChanged;
    }

    /// <summary>Точка входа для -executeMethod при запуске редактора из Python.</summary>
    public static void PlayScene()
    {
        string scene = GetArgument("-rsmaScene") ?? DefaultScene;
        // -executeMethod выполняется во время загрузки редактора: ждем, пока он будет готов
        EditorApplication.delayCall += () => OpenAndPlay(scene);
    }

    private static void WatchRequests()
    {
        if (EditorApplication.timeSinceStartup < nextCheck) return;
        nextCheck = EditorApplication.timeSinceStartup + 0.5;

        if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling) return;
        if (!File.Exists(RequestFile)) return;

        PlayRequest request;
        try
        {
            request = JsonUtility.FromJson<PlayRequest>(File.ReadAllText(RequestFile));
        }
        catch (Exception ex)
        {
            Debug.LogError($"[RSMALauncher] Bad request {RequestFile}: {ex.Message}");
            request = null;
        }
        File.Delete(RequestFile);
        if (request == null) return;

        MissionConfig.Set(request.config);
        Debug.Log($"[RSMALauncher] Запрос из Python: сцена {request.scene}");
        OpenAndPlay(string.IsNullOrEmpty(request.scene) ? DefaultScene : request.scene);
    }

    private static void OpenAndPlay(string scene)
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            return;

        var sceneAsset = AssetDatabase.LoadAssetAtPath<SceneAsset>(scene);
        if (sceneAsset == null)
        {
            Debug.LogError($"[RSMALauncher] Scene not found: {scene}");
            return;
        }

        // Несохраненные изменения в открытой сцене: спросить, как при обычном открытии сцены
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
            return;

        // Play всегда стартует с нужной сцены, даже если редактор восстановил другую
        EditorSceneManager.playModeStartScene = sceneAsset;
        SessionState.SetBool(StartSceneSetKey, true);

        Debug.Log($"[RSMALauncher] Opening {scene} and entering Play mode");
        EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
        EditorApplication.EnterPlaymode();
    }

    private static void OnPlayModeChanged(PlayModeStateChange state)
    {
        if (state != PlayModeStateChange.EnteredEditMode)
            return;

        // Обычный Play в редакторе снова работает с открытой сценой и ее собственными параметрами
        MissionConfig.Clear();
        if (SessionState.GetBool(StartSceneSetKey, false))
        {
            EditorSceneManager.playModeStartScene = null;
            SessionState.SetBool(StartSceneSetKey, false);
        }
    }

    private static string GetArgument(string name)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
                return args[i + 1];
        }
        return null;
    }
}
