using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Сборка SwarmDelivery (сцена Assets/1.unity) из командной строки:
///   Linux:   Unity -batchmode -quit -projectPath . -executeMethod SwarmDeliveryBuild.BuildLinux
///   Windows: Unity -batchmode -quit -projectPath . -executeMethod SwarmDeliveryBuild.BuildWindows
/// Результат: Builds/SwarmDelivery/SwarmDelivery.x86_64 (Linux), Builds/SwarmDeliveryWin/SwarmDelivery.exe (Windows).
/// Используется скриптами build.sh и build.bat, а также меню RSMA.
/// </summary>
public static class SwarmDeliveryBuild
{
    private static readonly string[] Scenes = { "Assets/1.unity" };
    private const string LinuxOutput = "Builds/SwarmDelivery/SwarmDelivery.x86_64";
    private const string WindowsOutput = "Builds/SwarmDeliveryWin/SwarmDelivery.exe";

    [MenuItem("RSMA/Build SwarmDelivery (Linux)")]
    public static void BuildLinux()
    {
        Build(BuildTarget.StandaloneLinux64, LinuxOutput);
    }

    [MenuItem("RSMA/Build SwarmDelivery (Windows)")]
    public static void BuildWindows()
    {
        Build(BuildTarget.StandaloneWindows64, WindowsOutput);
    }

    private static void Build(BuildTarget target, string outputPath)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));

        var options = new BuildPlayerOptions
        {
            scenes = Scenes,
            locationPathName = outputPath,
            target = target,
            options = BuildOptions.None
        };

        BuildReport report = BuildPipeline.BuildPlayer(options);
        Debug.Log($"[SwarmDeliveryBuild] {report.summary.result}: {outputPath}");

        if (Application.isBatchMode)
        {
            EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
        }
    }
}
