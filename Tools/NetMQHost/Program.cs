using System;
using System.Threading;
using RSMA.NetMQ;

// Usage: NetMQHost <port>
// Prints READY, then reads commands from stdin: state | stop | run | quit
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
}
