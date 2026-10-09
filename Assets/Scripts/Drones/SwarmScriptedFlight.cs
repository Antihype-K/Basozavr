using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Полёт роя мультироторов с грузом на тросах по заранее заданному маршруту.
/// Уставки дронам выдаёт сам скрипт, внешний Python-контроллер не требуется.
///
/// Маршрут задаётся в координатах ГРУЗА. Дроны строятся по окружности над ним,
/// высота строя считается из условия натянутого троса, а уставка ведётся с
/// ограничением скорости и ускорения — иначе груз на тросах раскачивается.
/// </summary>
public class SwarmScriptedFlight : MonoBehaviour
{
    [System.Serializable]
    public class Waypoint
    {
        public string label = "Точка";
        // Требуемое положение груза
        public Vector3 position;
        // Сколько держаться в точке после прихода, с
        public float holdTime = 0.0f;
        // Радиус, в котором точка считается достигнутой, м
        public float arriveRadius = 0.6f;
        // Отцепить груз после выдержки в этой точке
        public bool releaseHere = false;
        // Своя высота строя над точкой (0 — расчётная по натяжению троса)
        public float heightOverride = 0.0f;

        public Waypoint() { }

        public Waypoint(string label, Vector3 position, float holdTime = 0.0f,
                        float arriveRadius = 0.6f, bool releaseHere = false,
                        float heightOverride = 0.0f)
        {
            this.label = label;
            this.position = position;
            this.holdTime = holdTime;
            this.arriveRadius = arriveRadius;
            this.releaseHere = releaseHere;
            this.heightOverride = heightOverride;
        }
    }

    [Header("Состав роя")]
    public List<Quadrocopter> drones = new List<Quadrocopter>();
    public List<RSMACable> cables = new List<RSMACable>();
    public Rigidbody payload;

    [Header("Строй")]
    public float formationRadius = 1.414f;
    public float cableLength = 2.0f;
    // Должен совпадать со смещением, с которым дроны были расставлены при сборке
    public float formationAngleOffset = 0.0f;

    [Header("Маршрут")]
    public List<Waypoint> route = new List<Waypoint>();
    public bool autoStart = false;
    public bool loop = true;

    [Header("Ограничения движения")]
    // Крейсерская скорость переноса груза, м/с
    public float cruiseSpeed = 4.0f;
    // Скорость подъёма/опускания груза, м/с
    public float climbSpeed = 2.5f;
    // Ограничение вертикального ускорения, м/с^2 (0 — скорость набирается мгновенно).
    // Нужно для мягкой посадки груза на землю и плавного подъёма: без него груз касался земли на ~1,3 м/с
    public float climbAcceleration = 0.7f;
    // Ограничение ускорения уставки, м/с^2 — главное средство против раскачки
    public float acceleration = 0.5f;
    // Сдвиг строя по скорости груза, гасит маятник (0 — выключено)
    public float swingDamping = 0.0f;
    public float maxSwingShift = 1.0f;

    [Header("Страховка")]
    public float legTimeout = 90.0f;

    [Header("Отладка")]
    public bool verbose = true;
    public bool drawGizmos = true;

    public bool IsRunning { get; private set; }
    public int CurrentIndex { get; private set; }
    public string CurrentLabel => (route != null && CurrentIndex < route.Count) ? route[CurrentIndex].label : "—";
    public float DistanceToTarget { get; private set; }
    public float MissionTime { get; private set; }
    public float TraveledDistance { get; private set; }
    public int LapsDone { get; private set; }
    public bool PayloadAttached { get; private set; }
    public float FormationHeight { get; private set; }
    // Отклонение груза от оси строя, градусы
    public float SwingAngle { get; private set; }
    public float TotalTension { get; private set; }
    public float MinTension { get; private set; }
    public float MaxTension { get; private set; }
    public float PayloadSpeed { get; private set; }
    public float PayloadAltitude => payload != null ? payload.position.y : 0.0f;

    // Уставка положения груза: ведётся к точке маршрута с ограничением скорости
    private Vector3 setpoint;
    // Центр строя = уставка + компенсация раскачки
    private Vector3 formationCenter;
    private float horizontalSpeed;
    private float verticalSpeed;
    private float holdTimer;
    private float legTimer;
    private bool holding;
    private Vector3 lastTracked;
    // Куда возвращать груз на новом круге
    private Vector3 payloadHome;
    // Высота строя, применённая в последнем кадре (на посадке она своя)
    private float currentFormationHeight = 1.4f;

    void Start()
    {
        if (autoStart) StartRoute();
    }

    public void StartRoute()
    {
        if (route == null || route.Count == 0)
        {
            Debug.LogWarning("[SwarmFlight] Маршрут пуст — лететь некуда.");
            return;
        }

        if (drones == null || drones.Count == 0)
        {
            Debug.LogError("[SwarmFlight] Рой не задан — некому лететь.");
            return;
        }

        FormationHeight = ComputeFormationHeight();
        currentFormationHeight = FormationHeight;
        PayloadAttached = payload != null;
        payloadHome = payload != null ? payload.position : transform.position;

        setpoint = TrackedPosition;
        formationCenter = setpoint;
        lastTracked = setpoint;

        CurrentIndex = 0;
        holding = false;
        holdTimer = 0.0f;
        legTimer = 0.0f;
        horizontalSpeed = 0.0f;
        verticalSpeed = 0.0f;
        MissionTime = 0.0f;
        TraveledDistance = 0.0f;
        LapsDone = 0;
        IsRunning = true;

        if (verbose)
        {
            Debug.Log($"[SwarmFlight] Старт: дронов {drones.Count}, тросов {cables.Count}, " +
                      $"груз {(payload != null ? payload.mass : 0.0f):0.0} кг, " +
                      $"высота строя {FormationHeight:0.00} м, точек {route.Count}.");
        }
    }

    public void StopRoute()
    {
        IsRunning = false;
        if (verbose) Debug.Log("[SwarmFlight] Маршрут остановлен, рой удерживает строй.");
    }

    /// <summary>Положение, по которому оценивается выполнение маршрута.</summary>
    private Vector3 TrackedPosition
    {
        get
        {
            // С грузом ведём груз, после отцепки — виртуальную точку под строем
            if (PayloadAttached && payload != null) return payload.position;
            return SwarmCentroid() - Vector3.up * Mathf.Max(0.01f, currentFormationHeight);
        }
    }

    private Vector3 SwarmCentroid()
    {
        Vector3 sum = Vector3.zero;
        int n = 0;
        foreach (Quadrocopter d in drones)
        {
            if (d == null) continue;
            sum += d.transform.position;
            n++;
        }
        return n > 0 ? sum / n : transform.position;
    }

    /// <summary>
    /// Высота строя над грузом при натянутых тросах. Трос растягивается на
    /// T/k, поэтому длина и натяжение считаются итеративно.
    /// </summary>
    public float ComputeFormationHeight()
    {
        float g = Mathf.Abs(Physics.gravity.y);
        float m = payload != null ? payload.mass : 12.0f;
        int n = Mathf.Max(1, CableCount());
        float k = CableStiffness();

        // Радиус строя должен быть меньше длины троса, иначе груз не оторвать
        float r = Mathf.Min(formationRadius, cableLength * 0.85f);
        float length = cableLength;

        for (int i = 0; i < 6; i++)
        {
            float h = Mathf.Sqrt(Mathf.Max(0.01f, length * length - r * r));
            // Вертикальная составляющая: n * T * h / L = m * g
            float tension = (m * g * length) / (n * h);
            length = cableLength + tension / Mathf.Max(1.0f, k);
        }

        return Mathf.Sqrt(Mathf.Max(0.01f, length * length - r * r));
    }

    private int CableCount()
    {
        int n = 0;
        foreach (RSMACable c in cables)
        {
            if (c != null) n++;
        }
        return n > 0 ? n : drones.Count;
    }

    private float CableStiffness()
    {
        foreach (RSMACable c in cables)
        {
            if (c != null) return c.stiffness;
        }
        return 1000.0f;
    }

    void FixedUpdate()
    {
        float dt = Time.fixedDeltaTime;

        Vector3 tracked = TrackedPosition;
        TraveledDistance += Vector3.Distance(tracked, lastTracked);
        lastTracked = tracked;

        UpdateTelemetry();

        if (!IsRunning || route == null || route.Count == 0)
        {
            // Даже без маршрута держим строй, иначе рой просто упадёт
            ApplyFormation(FormationHeight);
            return;
        }

        MissionTime += dt;
        legTimer += dt;

        Waypoint wp = route[CurrentIndex];
        DistanceToTarget = Vector3.Distance(tracked, wp.position);

        float height = wp.heightOverride > 0.0f ? wp.heightOverride : FormationHeight;

        AdvanceSetpoint(wp, dt);
        ApplyFormation(height);

        if (!holding)
        {
            // Точка взята, только если и уставка доведена, и груз подтянулся
            bool setpointReached = Vector3.Distance(setpoint, wp.position) <= 0.05f;
            bool arrived = setpointReached && DistanceToTarget <= wp.arriveRadius;
            bool timedOut = legTimer > legTimeout;

            if (timedOut && verbose)
            {
                Debug.LogWarning($"[SwarmFlight] Точка '{wp.label}' не взята за {legTimeout:0} с " +
                                 $"(осталось {DistanceToTarget:0.0} м) — идём дальше.");
            }

            if (arrived || timedOut)
            {
                if (arrived && verbose)
                {
                    string load = PayloadAttached
                        ? $"натяжение тросов {TotalTension:0} Н, раскачка {SwingAngle:0.0}°"
                        : "порожняком";
                    Debug.Log($"[SwarmFlight] Точка '{wp.label}' достигнута за {legTimer:0.0} с, {load}.");
                }

                if (wp.holdTime > 0.0f)
                {
                    holding = true;
                    holdTimer = wp.holdTime;
                }
                else
                {
                    FinishWaypoint(wp);
                }
            }
        }
        else
        {
            holdTimer -= dt;
            if (holdTimer <= 0.0f) FinishWaypoint(wp);
        }
    }

    /// <summary>Ведение уставки с ограничением скорости и ускорения.</summary>
    private void AdvanceSetpoint(Waypoint wp, float dt)
    {
        Vector3 toTarget = wp.position - setpoint;

        // Горизонталь: трапецеидальный профиль со торможением на подходе
        Vector3 horizontal = new Vector3(toTarget.x, 0.0f, toTarget.z);
        float horizontalLeft = horizontal.magnitude;

        if (horizontalLeft > 1e-4f)
        {
            // Скорость, с которой ещё успеваем остановиться к точке
            float brakingSpeed = Mathf.Sqrt(2.0f * Mathf.Max(0.01f, acceleration) * horizontalLeft);
            float allowed = Mathf.Min(cruiseSpeed, brakingSpeed);

            horizontalSpeed = Mathf.MoveTowards(horizontalSpeed, allowed, acceleration * dt);
            float step = Mathf.Min(horizontalSpeed * dt, horizontalLeft);
            setpoint += (horizontal / horizontalLeft) * step;
        }
        else
        {
            horizontalSpeed = 0.0f;
            setpoint.x = wp.position.x;
            setpoint.z = wp.position.z;
        }

        // Вертикаль ведём отдельно и медленнее: подъём/спуск груза
        float verticalLeft = wp.position.y - setpoint.y;
        if (climbAcceleration > 0.0f)
        {
            // Разгон с ограничением ускорения и торможение перед целью, чтобы груз касался земли мягко
            float wanted = Mathf.Sign(verticalLeft) *
                           Mathf.Min(climbSpeed, Mathf.Sqrt(2.0f * climbAcceleration * Mathf.Abs(verticalLeft)));
            verticalSpeed = Mathf.MoveTowards(verticalSpeed, wanted, climbAcceleration * dt);
            setpoint.y = Mathf.MoveTowards(setpoint.y, wp.position.y, Mathf.Abs(verticalSpeed) * dt);
        }
        else
        {
            setpoint.y = Mathf.MoveTowards(setpoint.y, wp.position.y, climbSpeed * dt);
        }

        // Компенсация раскачки: строй идёт за грузом, гася маятник
        Vector3 shift = Vector3.zero;
        if (swingDamping > 0.0f && PayloadAttached && payload != null)
        {
            Vector3 payloadVel = payload.linearVelocity;
            Vector3 horizontalVel = new Vector3(payloadVel.x, 0.0f, payloadVel.z);
            shift = Vector3.ClampMagnitude(horizontalVel * swingDamping, maxSwingShift);
        }

        formationCenter = setpoint + shift;
    }

    /// <summary>Раздать дронам уставки по окружности вокруг центра строя.</summary>
    private void ApplyFormation(float height)
    {
        int n = drones.Count;
        if (n == 0) return;

        currentFormationHeight = height;

        float angleStep = 360.0f / n;
        float r = Mathf.Min(formationRadius, cableLength * 0.85f);

        for (int i = 0; i < n; i++)
        {
            Quadrocopter d = drones[i];
            if (d == null) continue;

            float angleRad = (i * angleStep + formationAngleOffset) * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(r * Mathf.Cos(angleRad), height, r * Mathf.Sin(angleRad));

            d.SetTargetPosition(formationCenter + offset);
        }
    }

    private void UpdateTelemetry()
    {
        TotalTension = 0.0f;
        MinTension = float.MaxValue;
        MaxTension = 0.0f;

        int counted = 0;
        foreach (RSMACable c in cables)
        {
            if (c == null || !c.enabled) continue;
            float f = c.currentForce;
            TotalTension += f;
            if (f < MinTension) MinTension = f;
            if (f > MaxTension) MaxTension = f;
            counted++;
        }
        if (counted == 0) MinTension = 0.0f;

        if (payload != null)
        {
            PayloadSpeed = payload.linearVelocity.magnitude;
        }

        // Угол имеет смысл только на тросах: после отцепки груз лежит на земле,
        // и «раскачка» выродилась бы в угол до места выгрузки
        if (PayloadAttached && payload != null)
        {
            Vector3 delta = SwarmCentroid() - payload.position;
            Vector3 horizontal = new Vector3(delta.x, 0.0f, delta.z);
            SwingAngle = Mathf.Atan2(horizontal.magnitude, Mathf.Max(0.01f, delta.y)) * Mathf.Rad2Deg;
        }
        else
        {
            SwingAngle = 0.0f;
        }
    }

    private void FinishWaypoint(Waypoint wp)
    {
        if (wp.releaseHere && PayloadAttached) ReleasePayload();

        holding = false;
        legTimer = 0.0f;
        horizontalSpeed = 0.0f;

        if (CurrentIndex + 1 < route.Count)
        {
            CurrentIndex++;
            return;
        }

        LapsDone++;

        if (loop)
        {
            CurrentIndex = 0;
            // Новый круг начинаем с тем же грузом на базе
            if (!PayloadAttached) AttachPayload();
            if (verbose) Debug.Log($"[SwarmFlight] Круг {LapsDone} завершён, маршрут повторяется.");
        }
        else
        {
            IsRunning = false;
            if (verbose)
            {
                Debug.Log($"[SwarmFlight] Миссия выполнена за {MissionTime:0.0} с, " +
                          $"груз перенесён на {TraveledDistance:0.0} м.");
            }
        }
    }

    /// <summary>Отцепка груза: тросы перестают тянуть и пропадают из кадра.</summary>
    public void ReleasePayload()
    {
        foreach (RSMACable c in cables)
        {
            if (c == null) continue;
            c.enabled = false;

            LineRenderer lr = c.GetComponent<LineRenderer>();
            if (lr != null) lr.enabled = false;
        }

        PayloadAttached = false;
        if (verbose) Debug.Log($"[SwarmFlight] Груз отцеплен на высоте {PayloadAltitude:0.00} м.");
    }

    /// <summary>Сцепка перед новым кругом: груз возвращается на базу, тросы включаются.</summary>
    public void AttachPayload()
    {
        if (payload == null) return;

        payload.position = payloadHome;
        payload.rotation = Quaternion.identity;
        payload.linearVelocity = Vector3.zero;
        payload.angularVelocity = Vector3.zero;

        foreach (RSMACable c in cables)
        {
            if (c == null) continue;
            c.enabled = true;

            LineRenderer lr = c.GetComponent<LineRenderer>();
            if (lr != null) lr.enabled = true;
        }

        PayloadAttached = true;
        lastTracked = payload.position;
        if (verbose) Debug.Log("[SwarmFlight] Груз закреплён на базе, тросы натянуты.");
    }

    void OnDrawGizmos()
    {
        if (!drawGizmos || route == null || route.Count == 0) return;

        Gizmos.color = Color.cyan;
        for (int i = 0; i < route.Count; i++)
        {
            Gizmos.DrawWireSphere(route[i].position, 0.4f);
            if (i + 1 < route.Count || loop)
            {
                Gizmos.DrawLine(route[i].position, route[(i + 1) % route.Count].position);
            }
        }

        if (!Application.isPlaying) return;

        // Строй и текущая уставка
        Gizmos.color = Color.yellow;
        float height = FormationHeight > 0.0f ? FormationHeight : 1.4f;
        Vector3 center = formationCenter + Vector3.up * height;
        Gizmos.DrawWireSphere(center, formationRadius);
        Gizmos.DrawLine(formationCenter, center);
    }
}
