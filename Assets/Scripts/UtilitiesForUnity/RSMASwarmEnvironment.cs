using RSMA.NetMQ;
using RSMA.uDTP;
using System;
using System.Collections.Generic;
using UnityEngine;

public class RSMASwarmEnvironment : MonoBehaviour
{
    [Header("Префабы и ссылки")]
    public GameObject dronePrefab;
    public GameObject payloadPrefab;

    public Vector3 startPosition = new Vector3(115, 0.18f, 96);

    [Header("Параметры роя")]
    public int numDrones = 6;
    public float payloadMass = 12.0f;
    public float radius = 1.414f;
    public float cableLength = 2.0f;

    [Header("Параметры троса")]
    public float cableStiffness = 1000.0f; // Н/м
    public float cableDamping = 35.0f;     // Н·с/м
    public float cableMaxForce = 250.0f;   // Н

    [Header("Ветер")]
    [Tooltip("Средняя скорость ветра, м/с (требование: до 8–10 м/с)")]
    public float windSpeed = 0.0f;
    [Tooltip("Амплитуда порывов, м/с")]
    public float gustAmplitude = 0.0f;
    [Tooltip("Направление ветра (куда дует), горизонтальная плоскость")]
    public Vector3 windDirection = new Vector3(0, 0, 1);
    [Tooltip("Cd·S дрона, м²")]
    public float droneDragArea = 0.1f;
    [Tooltip("Cd·S груза, м²")]
    public float payloadDragArea = 0.17f;

    [Header("Проверка отказоустойчивости")]
    [Tooltip("Номер дрона, который откажет (0 — без отказа)")]
    public int failDroneId = 0;
    [Tooltip("Время отказа от старта сцены, с")]
    public float failTime = 30.0f;

    [Header("Связь с Python")]
    [Tooltip("Запустить NetMQ-сервер для Python, если на сцене нет ServerApp")]
    public bool startServer = true;
    public int serverPort = 5555;

    [Header("Сборка")]
    // Снять галочку, если сцену собирает внешний сценарий (например SwarmDeliveryScene)
    public bool buildOnStart = true;

    [HideInInspector] public GameObject payloadInstance;
    [HideInInspector] public List<Quadrocopter> droneInstances = new List<Quadrocopter>();
    [HideInInspector] public List<RSMACable> cableInstances = new List<RSMACable>();

    public Vector3 CurrentWind { get; private set; }

    private const float AirDensity = 1.225f;
    private Rigidbody payloadRb;
    private Vector3 gustPhase;
    private RSMA.uDTP.Topics.Pose payloadPose;

    void Start()
    {
        // Повторный Run игнорируется, поэтому совместимо со сценами, где уже есть ServerApp
        if (startServer) NetMQServer.Run(serverPort);

        if (buildOnStart) BuildSwarmScene();
    }

    void Update()
    {
        // Выполняет команды Python (RestartLevel и т.п.) в главном потоке Unity
        if (startServer) NetMQServer.Update();
    }

    void FixedUpdate()
    {
        if (payloadRb == null) return;

        // Ветер: средняя скорость + порывы (сумма гармоник со случайными фазами)
        float t = Time.time;
        float gust = gustAmplitude * (0.6f * Mathf.Sin(0.9f * t + gustPhase.x)
                                    + 0.3f * Mathf.Sin(2.3f * t + gustPhase.y)
                                    + 0.1f * Mathf.Sin(5.1f * t + gustPhase.z));
        Vector3 direction = new Vector3(windDirection.x, 0.0f, windDirection.z).normalized;
        CurrentWind = direction * (windSpeed + gust);

        if (windSpeed != 0.0f || gustAmplitude != 0.0f)
        {
            foreach (Quadrocopter drone in droneInstances)
            {
                Rigidbody rb = drone.GetComponent<Rigidbody>();
                rb.AddForce(AerodynamicForce(CurrentWind - rb.linearVelocity, droneDragArea), ForceMode.Force);
            }
            payloadRb.AddForce(AerodynamicForce(CurrentWind - payloadRb.linearVelocity, payloadDragArea), ForceMode.Force);
        }

        // Отказ дрона по расписанию
        if (failDroneId > 0 && failDroneId <= droneInstances.Count && Time.timeSinceLevelLoad >= failTime
            && !droneInstances[failDroneId - 1].isFailed)
        {
            droneInstances[failDroneId - 1].isFailed = true;
            Debug.LogWarning($"[RSMA Engine] Отказ дрона {failDroneId} на {failTime} с");
        }

        // Состояние груза для Python: позиция/ориентация и скорость
        payloadPose.position = payloadRb.position;
        payloadPose.rotation = payloadRb.rotation;
        payloadPose.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        DataBroker.Publish("PayloadPose", payloadPose);
        DataBroker.Publish("PayloadVelocity", new RSMA.uDTP.Topics.Pose
        {
            position = payloadRb.linearVelocity,
            rotation = Quaternion.identity,
            timestamp = payloadPose.timestamp
        });
    }

    private static Vector3 AerodynamicForce(Vector3 relativeAirVelocity, float dragArea)
    {
        return 0.5f * AirDensity * dragArea * relativeAirVelocity.magnitude * relativeAirVelocity;
    }

    public void BuildSwarmScene()
    {
        // 1. Создание груза
        if (payloadPrefab != null)
        {
            payloadInstance = Instantiate(payloadPrefab, startPosition, Quaternion.identity);
        }
        else
        {
            payloadInstance = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            payloadInstance.transform.position = startPosition;
            payloadInstance.transform.localScale = Vector3.one * 0.4f;
            payloadInstance.GetComponent<Renderer>().material.color = Color.red;
        }

        payloadRb = payloadInstance.GetComponent<Rigidbody>();
        if (payloadRb == null) payloadRb = payloadInstance.AddComponent<Rigidbody>();
        payloadRb.mass = payloadMass;

        payloadRb.linearDamping = 0.2f;

        gustPhase = new Vector3(UnityEngine.Random.value, UnityEngine.Random.value, UnityEngine.Random.value) * 2.0f * Mathf.PI;

        // 2. Генерация дронов по кругу
        float angleStep = 360.0f / numDrones;
        float angleOffset = (numDrones == 4) ? 45.0f : 0.0f;

        for (int i = 0; i < numDrones; i++)
        {
            int droneId = i + 1;
            float angleRad = (i * angleStep + angleOffset) * Mathf.Deg2Rad;

            float dx = radius * Mathf.Cos(angleRad);
            float dz = radius * Mathf.Sin(angleRad);

            // Начальное положение дрона над грузом
            Vector3 initPos = startPosition + new Vector3(dx, 0.2f, dz);

            GameObject dObj;
            if (dronePrefab != null)
            {
                dObj = Instantiate(dronePrefab, initPos, Quaternion.identity);
            }
            else
            {
                dObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
                dObj.transform.position = initPos;
                dObj.transform.localScale = new Vector3(0.6f, 0.15f, 0.6f);
            }

            dObj.name = $"Quadrocopter_{droneId}";

            // Убеждаемся, что у дрона есть Rigidbody
            Rigidbody droneRb = dObj.GetComponent<Rigidbody>();
            if (droneRb == null)
            {
                droneRb = dObj.AddComponent<Rigidbody>();
                droneRb.mass = 2.5f; // Масса дрона из config.py
            }

            Quadrocopter droneScript = dObj.GetComponent<Quadrocopter>();
            if (droneScript == null) droneScript = dObj.AddComponent<Quadrocopter>();

            droneScript.droneId = droneId;
            droneInstances.Add(droneScript);

            // 3. Создание троса и безопасная инициализация
            GameObject cableObj = new GameObject($"Cable_{droneId}");
            cableObj.transform.SetParent(dObj.transform);

            RSMACable cableScript = cableObj.AddComponent<RSMACable>();

            cableScript.cableId = droneId;
            cableScript.mainBody = droneRb;
            cableScript.connectedBody = payloadRb;
            cableScript.restLength = cableLength;

            cableScript.stiffness = cableStiffness;
            cableScript.damping = cableDamping;
            cableScript.maxForce = cableMaxForce;

            cableScript.InitializeCable();
            cableInstances.Add(cableScript);
        }

        Debug.Log($"[RSMA Engine] Сцена успешно собрана: {numDrones} дронов, груз {payloadMass} кг.");
    }
}