using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Запуск сцены из командной строки (используется Python: scene.launcher.launch_unity):
///
///   Unity -projectPath &lt;проект&gt; -executeMethod RSMALauncher.PlayScene -rsmaScene Assets/Scenes/SupremeFlat.unity
///
/// Открывает сцену и входит в Play. Порт сервера RSMA передается переменной окружения
/// RSMA_PORT (читает ServerApp).
/// </summary>
public static class RSMALauncher
{
    public const string DefaultScene = "Assets/Scenes/SupremeFlat.unity";

    public static void PlayScene()
    {
        string scene = GetArgument("-rsmaScene") ?? DefaultScene;

        // -executeMethod выполняется во время загрузки редактора: ждем, пока он будет готов
        EditorApplication.delayCall += () =>
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
                return;

            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(scene) == null)
            {
                Debug.LogError($"[RSMALauncher] Scene not found: {scene}");
                return;
            }

            Debug.Log($"[RSMALauncher] Opening {scene} and entering Play mode");
            EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
            EditorApplication.EnterPlaymode();
        };
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
