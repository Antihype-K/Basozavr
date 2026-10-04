using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Запуск сцены из командной строки:
///   Unity -projectPath . -executeMethod BasozavrLauncher.Play [-scene Assets/Scenes/SupremeFlat.unity]
/// Открывает сцену и сразу входит в Play Mode. Используется скриптами run.sh / run.bat.
/// </summary>
public static class BasozavrLauncher
{
    private const string DefaultScene = "Assets/Scenes/SupremeFlat.unity";

    public static void Play()
    {
        string scene = GetArg("-scene") ?? DefaultScene;

        // Ждем, пока редактор полностью загрузит проект
        EditorApplication.delayCall += () =>
        {
            Debug.Log($"[BasozavrLauncher] Opening {scene}");
            EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
            EditorApplication.isPlaying = true;
        };
    }

    private static string GetArg(string name)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name) return args[i + 1];
        }
        return null;
    }
}
