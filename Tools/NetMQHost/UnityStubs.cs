// Minimal stand-ins for the UnityEngine/UnityEditor API used by the NetMQ server and uDTP topics.
using System;

namespace UnityEngine
{
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero => new Vector3(0, 0, 0);
        // Like Unity: extra properties that a plain serializer would also emit
        public Vector3 normalized => this;
        public float magnitude => (float)Math.Sqrt(x * x + y * y + z * z);
    }

    public struct Quaternion
    {
        public float x, y, z, w;
        public Quaternion(float x, float y, float z, float w) { this.x = x; this.y = y; this.z = z; this.w = w; }
        public static Quaternion identity => new Quaternion(0, 0, 0, 1);
        public Vector3 eulerAngles => new Vector3(0, 0, 0);
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
