using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Демонстрация основной задачи БАСозавра: рой мультироторов несёт груз на
/// тросах от базы до точки доставки, выгружает его и возвращается.
///
/// Сборку роя выполняет RSMASwarmEnvironment, движение — SwarmScriptedFlight.
/// Внешний Python-контроллер и брокер не нужны, достаточно нажать Play.
/// </summary>
[RequireComponent(typeof(RSMASwarmEnvironment))]
public class SwarmDeliveryScene : MonoBehaviour
{
    [Header("Точки миссии (XZ; высота берётся с рельефа)")]
    public Vector3 basePosition = new Vector3(115.0f, 0.0f, 85.0f);
    public Vector3 deliveryPosition = new Vector3(75.0f, 0.0f, 45.0f);
    public bool snapToGround = true;

    [Header("Профиль полёта")]
    public float cruiseHeight = 12.0f;
    public float dropHeight = 0.55f;
    public float unloadTime = 3.0f;
    public float hoverTime = 1.5f;
    public bool releasePayload = true;
    public bool loop = true;

    [Header("Ограничения движения")]
    public float cruiseSpeed = 4.0f;
    public float climbSpeed = 2.5f;
    // Плавные подъём и посадка груза (на модели: скорость касания 1,05 -> 0,44 м/с, пик натяжения 195 -> 175 Н)
    public float climbAcceleration = 0.7f;
    // Подобрано на модели сцены (Tools/SwarmModel): пик раскачки 5,3° -> 2,3° при +2,7 с на плече 56 м.
    // swingDamping > 0 увеличивает раскачку (сдвиг строя по скорости груза), поэтому выключен.
    public float acceleration = 0.5f;
    public float swingDamping = 0.0f;

    [Header("ПИД дронов под нагрузкой")]
    // Заводские настройки префаба (Kp=5) рассчитаны на полёт без груза:
    // натяжение троса такой регулятор отрабатывает слишком вяло
    public float positionKp = 40.0f;
    public float positionKi = 12.0f;
    public float positionKd = 14.0f;

    [Header("Внешнее управление (Python)")]
    // Рой собирается, но встроенная миссия не запускается: цели дронам задаёт Python-контроллер (папка Python/).
    // В сборке включается ключом командной строки: SwarmDelivery.x86_64 -python
    public bool externalControl = false;
    // ПИД под медленный полёт Python-контроллера (подобрано на модели Tools/SwarmModel)
    public float externalKp = 10.0f;
    public float externalKi = 2.0f;
    public float externalKd = 12.0f;

    [Header("Камера и HUD")]
    public bool followCamera = true;
    public bool showHud = true;

    [HideInInspector] public SwarmScriptedFlight flight;

    private RSMASwarmEnvironment environment;
    private Transform cameraFocus;

    private Vector3 basePoint;
    private Vector3 deliveryPoint;

    void Awake()
    {
        environment = GetComponent<RSMASwarmEnvironment>();
        // Параметры, заданные из Python (python Python/run.py --speed ... --height ...)
        MissionConfig.Apply(this, environment);
        if (System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-python") >= 0) externalControl = true;
        // Сцену загрузил Python командой LoadScene:...|python
        if (RSMA.NetMQ.NetMQServer.ExternalControlRequested) externalControl = true;
        // Рой собираем сами — после того, как точки привязаны к рельефу
        environment.buildOnStart = false;
    }

    void OnDestroy()
    {
        RSMA.NetMQ.NetMQServer.ExternalControlActive = false;
    }

    void Start()
    {
        basePoint = snapToGround ? GroundProbe.Resolve(basePosition) : basePosition;
        deliveryPoint = snapToGround ? GroundProbe.Resolve(deliveryPosition) : deliveryPosition;

        float legLength = Vector3.Distance(
            new Vector3(basePoint.x, 0.0f, basePoint.z),
            new Vector3(deliveryPoint.x, 0.0f, deliveryPoint.z));

        Debug.Log($"[SwarmDelivery] База {basePoint}, доставка {deliveryPoint}, плечо {legLength:0.0} м.");

        BuildMarker("Base", basePoint, new Color(0.25f, 0.65f, 1.0f));
        BuildMarker("DeliveryPoint", deliveryPoint, new Color(1.0f, 0.45f, 0.2f));

        // Груз стоит на базе, рой собирается вокруг него
        environment.startPosition = basePoint;
        environment.BuildSwarmScene();

        TuneDrones();
        // Python узнает режим сцены через GetSceneInfo
        RSMA.NetMQ.NetMQServer.ExternalControlActive = externalControl;
        if (externalControl)
        {
            Debug.Log("[SwarmDelivery] Внешнее управление: встроенная миссия отключена, ждём Python-контроллер (порт 5555).");
            // Живая визуализация в RSMA: статус миссии из Python, графики, след груза, маркер уставки
            SwarmLiveView view = gameObject.GetComponent<SwarmLiveView>();
            if (view == null) view = gameObject.AddComponent<SwarmLiveView>();
            view.environment = environment;
            // Пока нет команд, дроны держат стартовую позицию (без команды Quadrocopter не создаёт тягу)
            foreach (Quadrocopter d in environment.droneInstances)
            {
                if (d != null) d.SetTargetPosition(d.transform.position);
            }
        }
        else
        {
            SetUpFlight();
        }
        SetUpCamera();
    }

    /// <summary>ПИД дронов под груз: заводские коэффициенты префаба слишком мягкие.</summary>
    private void TuneDrones()
    {
        foreach (Quadrocopter d in environment.droneInstances)
        {
            if (d == null) continue;
            d.positionKp = externalControl ? externalKp : positionKp;
            d.positionKi = externalControl ? externalKi : positionKi;
            d.positionKd = externalControl ? externalKd : positionKd;
        }
    }

    private void SetUpFlight()
    {
        flight = gameObject.GetComponent<SwarmScriptedFlight>();
        if (flight == null) flight = gameObject.AddComponent<SwarmScriptedFlight>();

        flight.drones = environment.droneInstances;
        flight.cables = environment.cableInstances;
        flight.payload = environment.payloadInstance != null
            ? environment.payloadInstance.GetComponent<Rigidbody>()
            : null;

        flight.formationRadius = environment.radius;
        flight.cableLength = environment.cableLength;
        // Совпадает со смещением, с которым RSMASwarmEnvironment расставил дроны
        flight.formationAngleOffset = (environment.numDrones == 4) ? 45.0f : 0.0f;

        flight.cruiseSpeed = cruiseSpeed;
        flight.climbSpeed = climbSpeed;
        flight.climbAcceleration = climbAcceleration;
        flight.acceleration = acceleration;
        flight.swingDamping = swingDamping;

        flight.route = BuildDeliveryRoute();
        flight.loop = loop;
        // Запускаем вручную, чтобы не было двойного старта в Start()
        flight.autoStart = false;
        flight.StartRoute();
    }

    /// <summary>
    /// Миссия: натянуть тросы → поднять груз → перенести → выгрузить →
    /// вернуться порожняком → сесть.
    /// </summary>
    public List<SwarmScriptedFlight.Waypoint> BuildDeliveryRoute()
    {
        Vector3 b = (basePoint == Vector3.zero) ? basePosition : basePoint;
        Vector3 d = (deliveryPoint == Vector3.zero) ? deliveryPosition : deliveryPoint;

        Vector3 baseGround = b;
        Vector3 baseAir = b + Vector3.up * cruiseHeight;
        Vector3 deliveryAir = d + Vector3.up * cruiseHeight;
        Vector3 deliveryDrop = d + Vector3.up * dropHeight;

        return new List<SwarmScriptedFlight.Waypoint>
        {
            new SwarmScriptedFlight.Waypoint("Натяжение тросов", baseGround, 2.0f, 0.6f),
            new SwarmScriptedFlight.Waypoint("Подъём груза", baseAir, hoverTime, 0.5f),
            new SwarmScriptedFlight.Waypoint("Перенос груза", deliveryAir, hoverTime, 0.8f),
            new SwarmScriptedFlight.Waypoint("Выгрузка", deliveryDrop, unloadTime, 0.4f, releasePayload),
            new SwarmScriptedFlight.Waypoint("Подъём порожняком", deliveryAir, 1.0f, 0.8f),
            new SwarmScriptedFlight.Waypoint("Возврат на базу", baseAir, 1.0f, 0.8f),
            // На посадке строй опускается почти к земле, поэтому высота своя
            new SwarmScriptedFlight.Waypoint("Посадка", baseGround, 2.0f, 0.7f, false, 0.5f)
        };
    }

    private void BuildMarker(string name, Vector3 position, Color color)
    {
        GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        marker.name = name;
        marker.transform.position = new Vector3(position.x, position.y + 0.05f, position.z);
        marker.transform.localScale = new Vector3(3.0f, 0.02f, 3.0f);

        Collider col = marker.GetComponent<Collider>();
        if (col != null) Destroy(col);

        Renderer r = marker.GetComponent<Renderer>();
        if (r != null) r.material.color = color;
    }

    private void SetUpCamera()
    {
        if (!followCamera) return;

        Camera cam = Camera.main;
        if (cam == null) cam = FindFirstObjectByType<Camera>();
        if (cam == null)
        {
            Debug.LogWarning("[SwarmDelivery] Камера на сцене не найдена.");
            return;
        }

        // Точка съёмки: груз, пока он на тросах, дальше — сам рой
        GameObject focus = new GameObject("SwarmCameraFocus");
        cameraFocus = focus.transform;
        cameraFocus.position = basePoint;

        SwarmFollowCamera follow = cam.GetComponent<SwarmFollowCamera>();
        if (follow == null) follow = cam.gameObject.AddComponent<SwarmFollowCamera>();

        follow.target = cameraFocus;
        follow.offset = new Vector3(-11.0f, 8.0f, -11.0f);
        follow.lookAtHeight = 1.5f;

        cam.transform.position = cameraFocus.position + follow.offset;
        cam.transform.LookAt(cameraFocus.position + Vector3.up * follow.lookAtHeight);
    }

    private float statusTimer;

    // Статус встроенной миссии для Python (python Python/run.py показывает его в терминале)
    private void PublishStatus()
    {
        statusTimer -= Time.deltaTime;
        if (statusTimer > 0.0f) return;
        statusTimer = 0.2f;

        Vector3 payload = flight.payload != null ? flight.payload.position : basePoint;
        Vector2 toDelivery = new Vector2(deliveryPoint.x - payload.x, deliveryPoint.z - payload.z);
        float leg = Vector2.Distance(new Vector2(basePoint.x, basePoint.z), new Vector2(deliveryPoint.x, deliveryPoint.z));
        RSMA.uDTP.DataBroker.Publish("MissionStatus", new RSMA.uDTP.Topics.MissionStatus
        {
            timestamp = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            phase = flight.CurrentLabel,
            progress = leg > 0.01f ? Mathf.Clamp01(1.0f - toDelivery.magnitude / leg) : 1.0f,
            distanceToFinish = toDelivery.magnitude,
            setpoint = payload,
            finish = deliveryPoint
        });
    }

    void Update()
    {
        if (!externalControl && flight != null) PublishStatus();

        if (cameraFocus == null) return;

        if (externalControl)
        {
            // Без встроенной миссии камера следит за грузом
            if (environment.payloadInstance != null) cameraFocus.position = environment.payloadInstance.transform.position;
            return;
        }

        if (flight == null) return;

        // Update идёт до LateUpdate камеры, поэтому кадр не дёргается
        if (flight.PayloadAttached && flight.payload != null)
        {
            cameraFocus.position = flight.payload.position;
        }
        else
        {
            Vector3 sum = Vector3.zero;
            int n = 0;
            foreach (Quadrocopter d in flight.drones)
            {
                if (d == null) continue;
                sum += d.transform.position;
                n++;
            }
            if (n > 0) cameraFocus.position = sum / n - Vector3.up * 1.0f;
        }
    }

    void OnGUI()
    {
        if (showHud && externalControl) DrawExternalHud();
        if (!showHud || flight == null) return;

        float cargo = flight.payload != null ? flight.payload.mass : 0.0f;
        int droneCount = flight.drones != null ? flight.drones.Count : 0;
        string cargoState = flight.PayloadAttached ? "на тросах" : "выгружен";

        GUI.Box(new Rect(10, 10, 360, 170), "БАСозавр — доставка роем");
        GUI.Label(new Rect(22, 34, 340, 20),
            $"Рой: {droneCount} БПЛА   Груз: {cargo:0.0} кг ({cargoState})");
        GUI.Label(new Rect(22, 52, 340, 20), $"Этап: {flight.CurrentLabel}");
        GUI.Label(new Rect(22, 70, 340, 20), $"До точки: {flight.DistanceToTarget:0.0} м");
        GUI.Label(new Rect(22, 88, 340, 20),
            $"Груз: высота {flight.PayloadAltitude:0.0} м   скорость {flight.PayloadSpeed:0.0} м/с");
        string tension = flight.PayloadAttached
            ? $"{flight.TotalTension:0} Н (мин {flight.MinTension:0} / макс {flight.MaxTension:0})"
            : "тросы отцеплены";
        GUI.Label(new Rect(22, 106, 340, 20), $"Натяжение тросов: {tension}");
        GUI.Label(new Rect(22, 124, 340, 20),
            flight.PayloadAttached ? $"Раскачка груза: {flight.SwingAngle:0.0}°" : "Раскачка груза: —");
        GUI.Label(new Rect(22, 142, 340, 20),
            $"Путь: {flight.TraveledDistance:0.0} м   Время: {flight.MissionTime:0.0} с   Рейсов: {flight.LapsDone}");
    }

    private void DrawExternalHud()
    {
        Rigidbody payload = environment.payloadInstance != null ? environment.payloadInstance.GetComponent<Rigidbody>() : null;
        float total = 0.0f;
        foreach (RSMACable c in environment.cableInstances)
        {
            if (c != null) total += c.currentForce;
        }

        GUI.Box(new Rect(10, 10, 360, 90), "БАСозавр — управление из Python");
        GUI.Label(new Rect(22, 34, 340, 20), $"Рой: {environment.droneInstances.Count} БПЛА   Груз: {environment.payloadMass:0.0} кг");
        GUI.Label(new Rect(22, 52, 340, 20), payload != null
            ? $"Груз: высота {payload.position.y:0.0} м   скорость {payload.linearVelocity.magnitude:0.0} м/с"
            : "Груз: —");
        GUI.Label(new Rect(22, 70, 340, 20), $"Суммарное натяжение тросов: {total:0} Н");
    }

    void OnDrawGizmos()
    {
        Gizmos.color = new Color(0.25f, 0.65f, 1.0f);
        Gizmos.DrawWireSphere(basePosition, 1.5f);
        Gizmos.color = new Color(1.0f, 0.45f, 0.2f);
        Gizmos.DrawWireSphere(deliveryPosition, 1.5f);
    }
}
