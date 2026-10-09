using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Движение дрона по заранее заданному сценарию (маршруту), без внешнего
/// Python-контроллера: скрипт сам выдаёт уставки PID-регулятору Quadrocopter.
/// </summary>
[RequireComponent(typeof(Quadrocopter))]
public class DroneScriptedFlight : MonoBehaviour
{
    [System.Serializable]
    public class Waypoint
    {
        public string label = "Точка";
        public Vector3 position;
        // Сколько висеть в точке после прилёта, с
        public float holdTime = 0.0f;
        // Радиус, в котором точка считается достигнутой, м
        public float arriveRadius = 0.5f;

        public Waypoint() { }

        public Waypoint(string label, Vector3 position, float holdTime = 0.0f, float arriveRadius = 0.5f)
        {
            this.label = label;
            this.position = position;
            this.holdTime = holdTime;
            this.arriveRadius = arriveRadius;
        }
    }

    [Header("Маршрут")]
    public List<Waypoint> route = new List<Waypoint>();
    public bool autoStart = true;
    public bool loop = true;

    [Header("Страховка")]
    // Если дрон не уложился в это время на участке — летим к следующей точке
    public float legTimeout = 45.0f;

    [Header("Отладка")]
    public bool verbose = true;
    public bool drawGizmos = true;

    public bool IsRunning { get; private set; }
    public int CurrentIndex { get; private set; }
    public string CurrentLabel => (route != null && CurrentIndex < route.Count) ? route[CurrentIndex].label : "—";
    public float DistanceToTarget { get; private set; }
    public float TraveledDistance { get; private set; }
    public float MissionTime { get; private set; }
    public int LapsDone { get; private set; }

    private Quadrocopter drone;
    private float holdTimer;
    private float legTimer;
    private bool holding;
    private Vector3 lastPosition;

    void Awake()
    {
        drone = GetComponent<Quadrocopter>();
        lastPosition = transform.position;
    }

    void Start()
    {
        if (autoStart) StartRoute();
    }

    /// <summary>Задать маршрут списком координат (метки и выдержки по умолчанию).</summary>
    public void SetRoute(IEnumerable<Vector3> points, float holdTime = 0.0f)
    {
        route = new List<Waypoint>();
        int i = 1;
        foreach (Vector3 p in points)
        {
            route.Add(new Waypoint($"Точка {i++}", p, holdTime));
        }
    }

    public void StartRoute()
    {
        if (route == null || route.Count == 0)
        {
            Debug.LogWarning("[ScriptedFlight] Маршрут пуст — лететь некуда.");
            return;
        }

        CurrentIndex = 0;
        holding = false;
        holdTimer = 0.0f;
        legTimer = 0.0f;
        MissionTime = 0.0f;
        TraveledDistance = 0.0f;
        LapsDone = 0;
        IsRunning = true;

        ApplyTarget();
        if (verbose) Debug.Log($"[ScriptedFlight] Старт маршрута, точек: {route.Count}.");
    }

    public void StopRoute()
    {
        IsRunning = false;
        // Держим позицию, в которой остановились
        if (drone != null) drone.SetTargetPosition(transform.position);
        if (verbose) Debug.Log("[ScriptedFlight] Маршрут остановлен, дрон удерживает позицию.");
    }

    void Update()
    {
        // Пройденный путь считаем всегда — полезно для телеметрии на защите
        TraveledDistance += Vector3.Distance(transform.position, lastPosition);
        lastPosition = transform.position;

        if (!IsRunning || route == null || route.Count == 0) return;

        MissionTime += Time.deltaTime;
        legTimer += Time.deltaTime;

        Waypoint wp = route[CurrentIndex];
        DistanceToTarget = Vector3.Distance(transform.position, wp.position);

        if (!holding)
        {
            bool arrived = DistanceToTarget <= wp.arriveRadius;
            bool timedOut = legTimer > legTimeout;

            if (timedOut && verbose)
            {
                Debug.LogWarning($"[ScriptedFlight] Точка '{wp.label}' не достигнута за {legTimeout:0} с " +
                                 $"(осталось {DistanceToTarget:0.0} м) — идём дальше.");
            }

            if (arrived || timedOut)
            {
                if (arrived && verbose)
                {
                    Debug.Log($"[ScriptedFlight] Точка '{wp.label}' достигнута за {legTimer:0.0} с.");
                }

                if (wp.holdTime > 0.0f)
                {
                    holding = true;
                    holdTimer = wp.holdTime;
                }
                else
                {
                    NextWaypoint();
                }
            }
        }
        else
        {
            holdTimer -= Time.deltaTime;
            if (holdTimer <= 0.0f) NextWaypoint();
        }

        // Уставку обновляем каждый кадр: Quadrocopter ведёт по ней свой ПИД
        ApplyTarget();
    }

    private void NextWaypoint()
    {
        holding = false;
        legTimer = 0.0f;

        if (CurrentIndex + 1 < route.Count)
        {
            CurrentIndex++;
            return;
        }

        LapsDone++;

        if (loop)
        {
            CurrentIndex = 0;
            if (verbose) Debug.Log($"[ScriptedFlight] Круг {LapsDone} завершён, маршрут повторяется.");
        }
        else
        {
            IsRunning = false;
            if (verbose)
            {
                Debug.Log($"[ScriptedFlight] Маршрут завершён за {MissionTime:0.0} с, " +
                          $"пройдено {TraveledDistance:0.0} м.");
            }
        }
    }

    private void ApplyTarget()
    {
        if (drone == null || route == null || CurrentIndex >= route.Count) return;
        drone.SetTargetPosition(route[CurrentIndex].position);
    }

    void OnDrawGizmos()
    {
        if (!drawGizmos || route == null || route.Count == 0) return;

        Gizmos.color = Color.cyan;
        for (int i = 0; i < route.Count; i++)
        {
            Gizmos.DrawWireSphere(route[i].position, 0.35f);
            Vector3 next = route[(i + 1) % route.Count].position;
            if (i + 1 < route.Count || loop) Gizmos.DrawLine(route[i].position, next);
        }

        if (Application.isPlaying && CurrentIndex < route.Count)
        {
            Gizmos.color = Color.yellow;
            Gizmos.DrawLine(transform.position, route[CurrentIndex].position);
        }
    }
}
