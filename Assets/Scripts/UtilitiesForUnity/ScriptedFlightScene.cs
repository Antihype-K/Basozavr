using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Сборка демонстрационной сцены "полёт дрона по скрипту": площадка, дрон,
/// маршрут доставки и камера сопровождения. Ничего внешнего (Python, брокер)
/// не требуется — достаточно нажать Play.
/// </summary>
public class ScriptedFlightScene : MonoBehaviour
{
    [Header("Префаб дрона")]
    public GameObject dronePrefab;

    [Header("Точки миссии")]
    public Vector3 basePosition = new Vector3(0.0f, 0.1f, 0.0f);
    public Vector3 deliveryPosition = new Vector3(18.0f, 0.1f, 12.0f);

    [Header("Профиль полёта")]
    public float cruiseHeight = 6.0f;
    public float dropHeight = 1.2f;
    public float unloadTime = 3.0f;
    public float hoverTime = 1.0f;
    public bool loop = true;

    [Header("Окружение")]
    // Прижимать точки миссии к рельефу (Terrain) или к ближайшей поверхности под ними
    public bool snapToGround = true;
    public bool buildGround = true;
    public float groundSize = 120.0f;
    public bool followCamera = true;
    public bool showHud = true;

    [HideInInspector] public Quadrocopter droneInstance;
    [HideInInspector] public DroneScriptedFlight flightInstance;

    // Точки миссии после привязки к рельефу
    private Vector3 basePoint;
    private Vector3 deliveryPoint;

    void Start()
    {
        // На сцене с рельефом своя площадка не нужна
        bool hasTerrain = FindFirstObjectByType<Terrain>() != null;
        if (buildGround && !hasTerrain) BuildGround();

        basePoint = snapToGround ? GroundProbe.Resolve(basePosition) : basePosition;
        deliveryPoint = snapToGround ? GroundProbe.Resolve(deliveryPosition) : deliveryPosition;

        Debug.Log($"[ScriptedFlight] База {basePoint}, точка доставки {deliveryPoint}" +
                  (hasTerrain ? " (привязка к рельефу)." : "."));

        BuildMarker("Base", basePoint, new Color(0.25f, 0.65f, 1.0f));
        BuildMarker("DeliveryPoint", deliveryPoint, new Color(1.0f, 0.45f, 0.2f));

        SpawnDrone();
        SetUpCamera();
    }

    private void SpawnDrone()
    {
        Vector3 startPos = basePoint + Vector3.up * 0.2f;

        GameObject droneObj;
        if (dronePrefab != null)
        {
            droneObj = Instantiate(dronePrefab, startPos, Quaternion.identity);
        }
        else
        {
            // Аварийный вариант: если префаб не назначен, летает простой куб
            droneObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            droneObj.transform.position = startPos;
            droneObj.transform.localScale = new Vector3(0.6f, 0.15f, 0.6f);
            Debug.LogWarning("[ScriptedFlight] Префаб дрона не назначен — используется примитив.");
        }

        droneObj.name = "Quadrocopter_Scripted";

        Rigidbody rb = droneObj.GetComponent<Rigidbody>();
        if (rb == null) rb = droneObj.AddComponent<Rigidbody>();

        droneInstance = droneObj.GetComponent<Quadrocopter>();
        if (droneInstance == null) droneInstance = droneObj.AddComponent<Quadrocopter>();

        droneInstance.droneId = 1;
        // Без груза на тросе дрону хватает умеренной скорости и тяги
        droneInstance.maxSpeed = 6.0f;

        flightInstance = droneObj.GetComponent<DroneScriptedFlight>();
        if (flightInstance == null) flightInstance = droneObj.AddComponent<DroneScriptedFlight>();

        flightInstance.route = BuildDeliveryRoute();
        flightInstance.loop = loop;
        // Маршрут стартуем отсюда вручную, чтобы не было двойного запуска в Start()
        flightInstance.autoStart = false;
        flightInstance.StartRoute();

        Debug.Log($"[ScriptedFlight] Дрон создан в точке {startPos}, точек маршрута: {flightInstance.route.Count}.");
    }

    /// <summary>Типовая миссия доставки: взлёт → перелёт → выгрузка → возврат → посадка.</summary>
    public List<DroneScriptedFlight.Waypoint> BuildDeliveryRoute()
    {
        // Если сцена ещё не запущена, считаем маршрут по исходным координатам
        Vector3 b = (basePoint == Vector3.zero) ? basePosition : basePoint;
        Vector3 d = (deliveryPoint == Vector3.zero) ? deliveryPosition : deliveryPoint;

        Vector3 baseAir = b + Vector3.up * cruiseHeight;
        Vector3 deliveryAir = d + Vector3.up * cruiseHeight;
        Vector3 deliveryDrop = d + Vector3.up * dropHeight;

        return new List<DroneScriptedFlight.Waypoint>
        {
            new DroneScriptedFlight.Waypoint("Взлёт над базой", baseAir, hoverTime),
            new DroneScriptedFlight.Waypoint("Перелёт к точке доставки", deliveryAir, hoverTime),
            new DroneScriptedFlight.Waypoint("Снижение на выгрузку", deliveryDrop, unloadTime, 0.35f),
            new DroneScriptedFlight.Waypoint("Набор высоты", deliveryAir, hoverTime),
            new DroneScriptedFlight.Waypoint("Возврат на базу", baseAir, hoverTime),
            new DroneScriptedFlight.Waypoint("Посадка", b + Vector3.up * 0.25f, unloadTime, 0.3f)
        };
    }

    private void BuildGround()
    {
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = Vector3.zero;
        // Примитив Plane имеет размер 10x10 юнитов при масштабе 1
        ground.transform.localScale = Vector3.one * (groundSize / 10.0f);

        Renderer r = ground.GetComponent<Renderer>();
        if (r != null) r.material.color = new Color(0.30f, 0.34f, 0.30f);
    }

    private void BuildMarker(string name, Vector3 position, Color color)
    {
        GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        marker.name = name;
        marker.transform.position = new Vector3(position.x, position.y + 0.05f, position.z);
        marker.transform.localScale = new Vector3(2.0f, 0.02f, 2.0f);

        Collider col = marker.GetComponent<Collider>();
        if (col != null) Destroy(col);

        Renderer r = marker.GetComponent<Renderer>();
        if (r != null) r.material.color = color;
    }

    private void SetUpCamera()
    {
        if (!followCamera || droneInstance == null) return;

        Camera cam = Camera.main;
        if (cam == null) cam = FindFirstObjectByType<Camera>();
        if (cam == null)
        {
            Debug.LogWarning("[ScriptedFlight] Камера на сцене не найдена.");
            return;
        }

        SwarmFollowCamera follow = cam.GetComponent<SwarmFollowCamera>();
        if (follow == null) follow = cam.gameObject.AddComponent<SwarmFollowCamera>();

        follow.target = droneInstance.transform;
        follow.offset = new Vector3(-8.0f, 6.0f, -8.0f);
        follow.lookAtHeight = 0.5f;

        cam.transform.position = droneInstance.transform.position + follow.offset;
        cam.transform.LookAt(droneInstance.transform.position);
    }

    void OnGUI()
    {
        if (!showHud || flightInstance == null || droneInstance == null) return;

        Rigidbody rb = droneInstance.GetComponent<Rigidbody>();
        float speed = rb != null ? rb.linearVelocity.magnitude : 0.0f;

        GUI.Box(new Rect(10, 10, 330, 118), "БАСозавр — полёт по скрипту");
        GUI.Label(new Rect(22, 34, 310, 20), $"Этап: {flightInstance.CurrentLabel}");
        GUI.Label(new Rect(22, 52, 310, 20), $"До точки: {flightInstance.DistanceToTarget:0.0} м");
        GUI.Label(new Rect(22, 70, 310, 20), $"Высота: {droneInstance.transform.position.y:0.0} м   Скорость: {speed:0.0} м/с");
        GUI.Label(new Rect(22, 88, 310, 20), $"Пройдено: {flightInstance.TraveledDistance:0.0} м   Время: {flightInstance.MissionTime:0.0} с");
        GUI.Label(new Rect(22, 106, 310, 20), $"Кругов: {flightInstance.LapsDone}");
    }

    void OnDrawGizmos()
    {
        Gizmos.color = new Color(0.25f, 0.65f, 1.0f);
        Gizmos.DrawWireSphere(basePosition, 1.0f);
        Gizmos.color = new Color(1.0f, 0.45f, 0.2f);
        Gizmos.DrawWireSphere(deliveryPosition, 1.0f);
    }
}
