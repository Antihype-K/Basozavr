using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Сборка SwarmDelivery (сцена Assets/1.unity) под Linux:
///   Unity -batchmode -quit -projectPath . -executeMethod SwarmDeliveryBuild.BuildLinux
/// Результат: Builds/SwarmDelivery/SwarmDelivery.x86_64. Используется скриптом build.sh.
/// </summary>
public static class SwarmDeliveryBuild
{
    private static readonly string[] Scenes = { "Assets/1.unity" };
    private const string OutputPath = "Builds/SwarmDelivery/SwarmDelivery.x86_64";

    [MenuItem("RSMA/Build SwarmDelivery (Linux)")]
    public static void BuildLinux()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(OutputPath));

        var options = new BuildPlayerOptions
        {
            scenes = Scenes,
            locationPathName = OutputPath,
            target = BuildTarget.StandaloneLinux64,
            options = BuildOptions.None
        };

        BuildReport report = BuildPipeline.BuildPlayer(options);
        Debug.Log($"[SwarmDeliveryBuild] {report.summary.result}: {OutputPath}");

        if (Application.isBatchMode)
        {
            EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
        }
    }
}
