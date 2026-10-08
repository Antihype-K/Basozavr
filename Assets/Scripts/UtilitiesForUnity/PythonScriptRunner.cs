using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEngine;
using Debug = UnityEngine.Debug;

/// <summary>
/// Запуск Python-скриптов управления сценой (Python/Scripts) из терминала RSMA:
///
///   py                       — список скриптов
///   py 02_drone_square.py    — запустить скрипт (аргументы передаются дальше)
///   py_stop                  — остановить запущенные скрипты
///
/// Интерпретатор: переменная окружения RSMA_PYTHON, иначе "python" (Windows) / "python3".
/// Папка скриптов: переменная RSMA_PYTHON_SCRIPTS, иначе &lt;проект&gt;/Python/Scripts.
/// Вывод скрипта попадает в консоль Unity.
/// </summary>
public static class PythonScriptRunner
{
    private static readonly List<Process> _processes = new List<Process>();

    public static string ScriptsDirectory
    {
        get
        {
            string fromEnv = Environment.GetEnvironmentVariable("RSMA_PYTHON_SCRIPTS");
            if (!string.IsNullOrEmpty(fromEnv)) return fromEnv;
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Python", "Scripts"));
        }
    }

    public static string PythonExecutable
    {
        get
        {
            string fromEnv = Environment.GetEnvironmentVariable("RSMA_PYTHON");
            if (!string.IsNullOrEmpty(fromEnv)) return fromEnv;
            return Application.platform == RuntimePlatform.WindowsPlayer ||
                   Application.platform == RuntimePlatform.WindowsEditor ? "python" : "python3";
        }
    }

    public static string ListScripts()
    {
        string dir = ScriptsDirectory;
        if (!Directory.Exists(dir))
            return $"Python scripts folder not found: {dir}";

        var names = Directory.GetFiles(dir, "*.py")
            .Select(Path.GetFileName)
            .Where(n => !n.StartsWith("_"))
            .OrderBy(n => n);
        return "Python scripts: " + string.Join(", ", names);
    }

    public static string Run(string script, IEnumerable<string> args)
    {
        string path = Path.IsPathRooted(script) ? script : Path.Combine(ScriptsDirectory, script);
        if (!path.EndsWith(".py")) path += ".py";
        if (!File.Exists(path))
            return $"Script not found: {path}";

        var info = new ProcessStartInfo
        {
            FileName = PythonExecutable,
            // -u: вывод без буферизации, чтобы строки сразу появлялись в консоли
            Arguments = $"-u \"{path}\" " + string.Join(" ", args.Select(a => $"\"{a}\"")),
            WorkingDirectory = Path.GetDirectoryName(path),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        info.StandardOutputEncoding = System.Text.Encoding.UTF8;
        info.StandardErrorEncoding = System.Text.Encoding.UTF8;

        string name = Path.GetFileName(path);
        try
        {
            var process = new Process { StartInfo = info, EnableRaisingEvents = true };
            // Debug.Log можно вызывать из любого потока
            process.OutputDataReceived += (_, e) => { if (e.Data != null) Debug.Log($"[py {name}] {e.Data}"); };
            process.ErrorDataReceived += (_, e) => { if (e.Data != null) Debug.LogWarning($"[py {name}] {e.Data}"); };
            process.Exited += (_, __) =>
            {
                Debug.Log($"[py {name}] finished with code {process.ExitCode}");
                lock (_processes) _processes.Remove(process);
            };

            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            lock (_processes) _processes.Add(process);
            return $"Started {name} (pid {process.Id})";
        }
        catch (Exception ex)
        {
            return $"Cannot start {PythonExecutable}: {ex.Message}. Set RSMA_PYTHON to the python executable";
        }
    }

    public static string StopAll()
    {
        int count = 0;
        lock (_processes)
        {
            foreach (var process in _processes.ToArray())
            {
                try
                {
                    if (!process.HasExited)
                    {
                        process.Kill();
                        count++;
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[py] Cannot stop process: {ex.Message}");
                }
            }
            _processes.Clear();
        }
        return $"Stopped {count} script(s)";
    }

    [RuntimeInitializeOnLoadMethod]
    private static void StopOnQuit()
    {
        Application.quitting += () => StopAll();
    }
}
