using System;
using System.Threading;
using RSMA.NetMQ;

// Usage: NetMQHost <port>
// Prints READY, then reads commands from stdin: state | stop | run | quit | lease <robot>
public static class Program
{
    public static int Main(string[] args)
    {
        int port = int.Parse(args[0]);
        NetMQServer.Run(port);

        // Stand-in for ServerApp.Update() on the Unity main thread
        var mainThread = new Thread(() =>
        {
            while (true)
            {
                NetMQServer.Update();
                Thread.Sleep(5);
            }
        }) { IsBackground = true };
        mainThread.Start();

        Thread.Sleep(200);
        Console.WriteLine("READY");

        string line;
        while ((line = Console.ReadLine()) != null)
        {
            string[] parts = line.Trim().Split(' ');
            if (parts[0] == "lease" && parts.Length > 1)
            {
                // ExternalControl.Level() is called from the Unity main thread in the real scene
                int level = 0;
                RunOnMainThread(() => level = RSMA.uDTP.ExternalControl.Level(parts[1]));
                Console.WriteLine($"level={level}");
                continue;
            }

            switch (line.Trim())
            {
                case "state":
                    break;
                case "stop":
                    NetMQServer.Stop();
                    Thread.Sleep(300);
                    break;
                case "run":
                    NetMQServer.Run(port);
                    Thread.Sleep(300);
                    break;
                case "quit":
                    NetMQServer.Stop();
                    return 0;
                default:
                    Console.WriteLine($"unknown command {line}");
                    continue;
            }
            Console.WriteLine($"running={NetMQServer.IsRunning.ToString().ToLowerInvariant()}");
        }
        return 0;
    }

    private static void RunOnMainThread(Action action)
    {
        var done = new ManualResetEventSlim();
        NetMQServer.EnqueueAction(() => { action(); done.Set(); });
        done.Wait(2000);
    }
}
