// Minimal stand-ins for the UnityEngine/UnityEditor API used by the NetMQ server and uDTP topics.
using System;

namespace UnityEngine
{
    public struct Vector3 { public float x, y, z; }
    public struct Quaternion { public float x, y, z, w; }

    public static class Time
    {
        private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
        public static float realtimeSinceStartup => (float)Clock.Elapsed.TotalSeconds;
    }

    public static class Debug
    {
        public static void Log(object message) => Console.Error.WriteLine(message);
        public static void LogError(object message) => Console.Error.WriteLine(message);
    }

    public static class Application
    {
        public static event Action quitting;
    }

    namespace SceneManagement
    {
        public struct Scene { public string name; }

        public static class SceneManager
        {
            public static Scene GetActiveScene() => default;
            public static void LoadScene(string name) => Console.Error.WriteLine($"LoadScene {name}");
        }
    }
}

namespace UnityEditor
{
    public enum PlayModeStateChange { ExitingPlayMode }

    public static class EditorApplication
    {
        public static event Action<PlayModeStateChange> playModeStateChanged;
    }
}
