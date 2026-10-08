using NetMQ;
using NetMQ.Sockets;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using RSMA.uDTP;
using RSMA.uDTP.Topics;
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace RSMA.NetMQ
{
    public static class NetMQServer
    {
        private static volatile bool _isRunning;
        private static Task _serverTask;
        private static readonly TimeSpan ReceiveTimeout = TimeSpan.FromMilliseconds(100);
        private static readonly Queue<Action> _actionQueue = new Queue<Action>();
        private static readonly object _queueLock = new object();

        private static readonly JsonSerializerSettings JsonSettings = new JsonSerializerSettings
        {
            ReferenceLoopHandling = ReferenceLoopHandling.Ignore,
            NullValueHandling = NullValueHandling.Ignore,
            ContractResolver = new CamelCasePropertyNamesContractResolver()
        };
        public static bool IsRunning => _isRunning;

        static NetMQServer()
        {
        #if UNITY_EDITOR
            UnityEditor.EditorApplication.playModeStateChanged += (state) =>
            {
                if (state == UnityEditor.PlayModeStateChange.ExitingPlayMode)
                {
                    Stop();
                }
            };
        #endif

            Application.quitting += () =>
            {
                Stop();
                // Даем циклу сервера закрыть сокет, иначе выход из приложения может зависнуть
                _serverTask?.Wait(500);
            };
        }

        public static void Run(int serverPort = 5555)
        {
            if (_isRunning) return;

            // Предыдущий цикл мог еще не освободить порт
            _serverTask?.Wait(1000);

            _isRunning = true;
            _serverTask = Task.Run(() => ServerLoop(serverPort));
        }

        /// <summary>
        /// Останавливает сервер. Цикл завершится в течение ReceiveTimeout и сам освободит порт.
        /// </summary>
        public static void Stop()
        {
            _isRunning = false;
        }

        private static void ServerLoop(int serverPort)
        {
            try
            {
                AsyncIO.ForceDotNet.Force();
                using (var server = new RouterSocket())
                {
                    server.Bind($"tcp://*:{serverPort}");

                    NetMQMessage message = null;
                    while (_isRunning)
                    {
                        // Ждем с таймаутом, чтобы Stop() срабатывал без входящих сообщений
                        if (!server.TryReceiveMultipartMessage(ReceiveTimeout, ref message))
                            continue;

                        // Router сообщение в формате: [Identity, EmptyFrame, Data]
                        if (message.FrameCount < 3)
                            continue;

                        var clientIdentity = message[0];
                        byte[] rawBytes = message[message.FrameCount - 1].ToByteArray();
                        string payload = Encoding.UTF8.GetString(rawBytes).Trim();

                        string response = ProcessCommand(payload);
                        byte[] responseBytes = Encoding.UTF8.GetBytes(response);

                        // Отправляем ответ обратно тому же клиенту
                        server.SendMultipartMessage(new NetMQMessage(new[]
                        {
                            clientIdentity,
                            NetMQFrame.Empty,
                            new NetMQFrame(responseBytes)
                        }));
                    }
                }
            }
            catch (Exception ex)
            {
                // Например, порт занят: без этого исключение терялось в Task, а UI показывал "Online"
                _isRunning = false;
                string error = ex.Message;
                EnqueueAction(() => Debug.LogError($"[NetMQServer] Server stopped: {error}"));
            }
            finally
            {
                NetMQConfig.Cleanup(false);
            }
        }

        private static string ErrorJson(string message)
        {
            return JsonConvert.SerializeObject(new NetworkResponse { Status = "error", Message = message }, JsonSettings);
        }

        private static string ProcessCommand(string command)
        {
            if (string.IsNullOrWhiteSpace(command))
                return ErrorJson("Empty payload");

            if (command.Trim().StartsWith("{") && command.Trim().EndsWith("}"))
            {
                try
                {
                    var packet = JsonConvert.DeserializeObject<NetworkPacket>(command);

                    if (packet != null && packet.Action == "batch")
                    {
                        return ProcessBatch(packet.Data);
                    }

                    if (packet != null && !string.IsNullOrEmpty(packet.Action) && !string.IsNullOrEmpty(packet.TopicType))
                    {
                        return ProcessBrokerCommand(packet);
                    }
                }
                catch
                {
                    // Если десериализация упала, значит это был не пакет брокера, 
                    // либо JSON поврежден. Идем дальше к обычным командам.
                }
            }

            if (command.StartsWith("PrintMessage:"))
            {
                string msg = command.Substring("PrintMessage:".Length);
                EnqueueAction(() => Debug.Log($"Message: {msg}"));
                return "OK: Message printed";
            }
            else if (command.StartsWith("RestartLevel"))
            {
                EnqueueAction(() =>
                {
                    UnityEngine.SceneManagement.SceneManager.LoadScene(
                        UnityEngine.SceneManagement.SceneManager.GetActiveScene().name
                    );
                });
                return "OK: Level restarting";
            }
            else if (command.StartsWith("GetServerStatus"))
            {
                return "OK: Server is running";
            }
            else 
            {
                return $"Error: Unknown command '{command}'";
            }


        }

        // Потокобезопасная очередь для выполнения в основном потоке Unity
        public static void EnqueueAction(Action action)
        {
            lock (_queueLock) { _actionQueue.Enqueue(action); }
        }

        // Метод, который нужно вызывать в Update любого MonoBehaviour
        public static void Update()
        {
            // Забираем действия под замком, а выполняем без него: действие может само вызвать
            // EnqueueAction, а исключение в одном действии не должно терять остальные
            Action[] actions;
            lock (_queueLock)
            {
                if (_actionQueue.Count == 0) return;
                actions = _actionQueue.ToArray();
                _actionQueue.Clear();
            }

            foreach (var action in actions)
            {
                try
                {
                    action.Invoke();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[NetMQServer] Action failed: {ex}");
                }
            }
        }

        /// <summary>
        /// Несколько команд брокера за один запрос: Data — JSON-массив пакетов
        /// (как у publish/get). Ответ: data — JSON-массив ответов на каждый пакет по порядку.
        /// Экономит сетевые round-trip: клиент управления роем делает 2 запроса за шаг вместо 19.
        /// </summary>
        private static string ProcessBatch(string data)
        {
            List<NetworkPacket> packets;
            try
            {
                packets = JsonConvert.DeserializeObject<List<NetworkPacket>>(data ?? "[]");
            }
            catch (Exception ex)
            {
                return ErrorJson($"Bad batch: {ex.Message}");
            }

            var responses = new List<string>(packets?.Count ?? 0);
            if (packets != null)
            {
                foreach (var packet in packets)
                {
                    if (packet == null || string.IsNullOrEmpty(packet.Action) || string.IsNullOrEmpty(packet.TopicType))
                        responses.Add(ErrorJson("Batch item must have Action and TopicType"));
                    else
                        responses.Add(ProcessBrokerCommand(packet));
                }
            }

            return JsonConvert.SerializeObject(
                new NetworkResponse { Status = "ok", Data = JsonConvert.SerializeObject(responses) }, JsonSettings);
        }

        // Кэш рефлексии: тип топика и generic-методы DataBroker ищутся один раз на тип.
        // Используется только из потока сервера.
        private static readonly Dictionary<string, (Type type, MethodInfo publish, MethodInfo get)> _topicCache =
            new Dictionary<string, (Type, MethodInfo, MethodInfo)>();

        private static bool TryGetTopic(string topicTypeName, out (Type type, MethodInfo publish, MethodInfo get) topic)
        {
            if (_topicCache.TryGetValue(topicTypeName, out topic))
                return true;

            Type topicType = Type.GetType("RSMA.uDTP.Topics." + topicTypeName);
            if (topicType == null)
                return false;

            var flags = BindingFlags.Public | BindingFlags.Static;
            topic = (
                topicType,
                typeof(RSMA.uDTP.DataBroker).GetMethod("Publish", flags).MakeGenericMethod(topicType),
                typeof(RSMA.uDTP.DataBroker).GetMethod("GetState", flags).MakeGenericMethod(topicType));
            _topicCache[topicTypeName] = topic;
            return true;
        }

        private static string ProcessBrokerCommand(NetworkPacket packet)
        {
            try
            {
                if (!TryGetTopic(packet.TopicType, out var topic))
                {
                    return ErrorJson($"Type '{packet.TopicType}' not found");
                }

                if (packet.Action == "publish")
                {
                    object deserializedData = JsonConvert.DeserializeObject(packet.Data, topic.type, JsonSettings);

                    // DataBroker.Publish<TargetType>(packet.TopicName, deserializedData)
                    topic.publish.Invoke(null, new object[] { packet.TopicName, deserializedData });

                    return JsonConvert.SerializeObject(new NetworkResponse { Status = "ok" }, JsonSettings);
                }

                else if (packet.Action == "get")
                {
                    // DataBroker.GetState<TargetType>(packet.TopicName)
                    object state = topic.get.Invoke(null, new object[] { packet.TopicName });

                    // Сериализуем полученный объект (даже если он default/null) back to JSON
                    string dataJson = JsonConvert.SerializeObject(state, JsonSettings);
                    return JsonConvert.SerializeObject(new NetworkResponse { Status = "ok", Data = dataJson }, JsonSettings);
                }
            }
            catch (Exception ex)
            {
                // Если ошибка произошла внутри Invoke, реальное исключение будет в InnerException
                string errorMsg = ex.InnerException != null ? ex.InnerException.Message : ex.Message;
                return ErrorJson($"Reflection error: {errorMsg}");
            }
            return ErrorJson($"Unknown action '{packet.Action}'");
        }
    }
}