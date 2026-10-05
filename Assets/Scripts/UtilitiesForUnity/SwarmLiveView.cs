using System;
using System.Collections.Generic;
using RSMA.uDTP;
using RSMA.uDTP.Topics;
using UnityEngine;

/// <summary>
/// Визуализация полёта роя внутри RSMA при управлении из Python: панель статуса миссии, живые графики
/// (раскачка груза, натяжение тросов, высота груза), след груза и маркер уставки.
/// Статус берётся из топика MissionStatus, который публикует Python/control/swarm_controller.py;
/// раскачка, натяжение и высота считаются здесь по состоянию физики.
/// </summary>
public class SwarmLiveView : MonoBehaviour
{
    public RSMASwarmEnvironment environment;

    [Header("Графики")]
    public float sampleRate = 20.0f;
    public float historySeconds = 90.0f;
    public Vector2 panelOrigin = new Vector2(10.0f, 110.0f);
    public float panelWidth = 360.0f;

    [Header("3D")]
    public bool drawTrail = true;
    public bool drawSetpointMarker = true;
    public string statusTopic = "MissionStatus";

    private class Series
    {
        public readonly List<float> values = new List<float>();
        public Color color;
        public Series(Color color) { this.color = color; }
    }

    private readonly Series swing = new Series(new Color(1.0f, 0.55f, 0.2f));
    private readonly Series tensionTotal = new Series(new Color(0.35f, 0.75f, 1.0f));
    private readonly Series tensionMin = new Series(new Color(0.55f, 0.9f, 0.55f));
    private readonly Series tensionMax = new Series(new Color(1.0f, 0.4f, 0.4f));
    private readonly Series height = new Series(new Color(0.9f, 0.85f, 0.3f));

    private MissionStatus status;
    private long lastStatusTimestamp = -1;
    private float lastStatusReceived = -100.0f;
    private float sampleTimer;
    private int capacity;

    private Rigidbody payloadBody;
    private GameObject setpointMarker;

    private float swingNow, totalNow, minNow, maxNow, heightNow, speedNow;

    void Start()
    {
        if (environment == null) environment = GetComponent<RSMASwarmEnvironment>();
        capacity = Mathf.Max(10, Mathf.RoundToInt(sampleRate * historySeconds));
    }

    void Update()
    {
        if (environment == null || environment.payloadInstance == null) return;

        if (payloadBody == null)
        {
            payloadBody = environment.payloadInstance.GetComponent<Rigidbody>();
            if (drawTrail) AddTrail(environment.payloadInstance);
            if (drawSetpointMarker) setpointMarker = BuildMarker();
        }

        ReadStatus();
        Measure();

        sampleTimer += Time.deltaTime;
        float period = 1.0f / Mathf.Max(1.0f, sampleRate);
        while (sampleTimer >= period)
        {
            sampleTimer -= period;
            Push(swing, swingNow);
            Push(tensionTotal, totalNow);
            Push(tensionMin, minNow);
            Push(tensionMax, maxNow);
            Push(height, heightNow);
        }

        if (setpointMarker != null)
        {
            bool alive = StatusAlive;
            setpointMarker.SetActive(alive);
            if (alive) setpointMarker.transform.position = status.setpoint;
        }
    }

    private bool StatusAlive => Time.time - lastStatusReceived < 2.0f;

    private void ReadStatus()
    {
        MissionStatus s = DataBroker.GetState<MissionStatus>(statusTopic);
        if (s.timestamp != lastStatusTimestamp)
        {
            lastStatusTimestamp = s.timestamp;
            lastStatusReceived = Time.time;
        }
        status = s;
    }

    private void Measure()
    {
        Vector3 centroid = Vector3.zero;
        int n = 0;
        foreach (Quadrocopter d in environment.droneInstances)
        {
            if (d == null) continue;
            centroid += d.transform.position;
            n++;
        }
        if (n > 0) centroid /= n;

        Vector3 payloadPosition = payloadBody != null ? payloadBody.position : environment.payloadInstance.transform.position;
        Vector3 delta = centroid - payloadPosition;
        Vector3 horizontal = new Vector3(delta.x, 0.0f, delta.z);
        swingNow = n > 0 ? Mathf.Atan2(horizontal.magnitude, Mathf.Max(0.01f, delta.y)) * Mathf.Rad2Deg : 0.0f;

        totalNow = 0.0f;
        minNow = float.MaxValue;
        maxNow = 0.0f;
        int cables = 0;
        foreach (RSMACable c in environment.cableInstances)
        {
            if (c == null) continue;
            float f = c.currentForce;
            totalNow += f;
            if (f < minNow) minNow = f;
            if (f > maxNow) maxNow = f;
            cables++;
        }
        if (cables == 0) minNow = 0.0f;

        heightNow = payloadPosition.y;
        speedNow = payloadBody != null ? payloadBody.linearVelocity.magnitude : 0.0f;
    }

    private void Push(Series s, float value)
    {
        s.values.Add(value);
        if (s.values.Count > capacity) s.values.RemoveAt(0);
    }

    private static void AddTrail(GameObject payload)
    {
        TrailRenderer trail = payload.GetComponent<TrailRenderer>();
        if (trail == null) trail = payload.AddComponent<TrailRenderer>();
        trail.time = 60.0f;
        trail.startWidth = 0.15f;
        trail.endWidth = 0.02f;
        trail.minVertexDistance = 0.1f;
        trail.material = new Material(Shader.Find("Sprites/Default"));
        trail.startColor = new Color(1.0f, 0.9f, 0.2f, 1.0f);
        trail.endColor = new Color(1.0f, 0.9f, 0.2f, 0.0f);
    }

    private static GameObject BuildMarker()
    {
        GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        marker.name = "PythonSetpoint";
        marker.transform.localScale = Vector3.one * 0.4f;
        Collider col = marker.GetComponent<Collider>();
        if (col != null) Destroy(col);
        Renderer r = marker.GetComponent<Renderer>();
        if (r != null) r.material.color = new Color(0.2f, 1.0f, 1.0f);
        marker.SetActive(false);
        return marker;
    }

    // ---------------------------------------------------------------- GUI

    void OnGUI()
    {
        if (environment == null) return;

        float x = panelOrigin.x;
        float y = panelOrigin.y;

        DrawStatus(new Rect(x, y, panelWidth, 118.0f));
        y += 124.0f;
        DrawChart(new Rect(x, y, panelWidth, 92.0f), "Раскачка груза, °", swing);
        y += 98.0f;
        DrawChart(new Rect(x, y, panelWidth, 92.0f), "Натяжение тросов, Н (сумма / мин / макс)",
                  tensionTotal, tensionMin, tensionMax);
        y += 98.0f;
        DrawChart(new Rect(x, y, panelWidth, 92.0f), "Высота груза, м", height);
    }

    private void DrawStatus(Rect r)
    {
        GUI.Box(r, "Python-контроллер");
        string phase;
        if (!StatusAlive)
        {
            phase = "нет связи (python Python/main.py)";
        }
        else
        {
            phase = PhaseLabel(status.phase);
        }

        GUI.Label(new Rect(r.x + 12, r.y + 22, r.width - 24, 20), $"Фаза: {phase}");
        if (StatusAlive)
        {
            GUI.Label(new Rect(r.x + 12, r.y + 40, r.width - 24, 20),
                      $"До финиша: {status.distanceToFinish:0.0} м   Маршрут: {status.progress * 100.0f:0}%");
        }
        GUI.Label(new Rect(r.x + 12, r.y + 58, r.width - 24, 20),
                  $"Груз: высота {heightNow:0.0} м   скорость {speedNow:0.0} м/с");
        GUI.Label(new Rect(r.x + 12, r.y + 76, r.width - 24, 20),
                  $"Раскачка: {swingNow:0.0}°   Натяжение: {totalNow:0} Н (мин {minNow:0} / макс {maxNow:0})");
        GUI.Label(new Rect(r.x + 12, r.y + 94, r.width - 24, 20),
                  $"Дронов: {environment.droneInstances.Count}   Груз: {environment.payloadMass:0.0} кг");
    }

    private static string PhaseLabel(string phase)
    {
        switch (phase)
        {
            case "LIFT": return "подъём груза";
            case "TRAJECTORY": return "перенос по траектории";
            case "HOVER": return "стабилизация над точкой";
            case "LAND": return "посадка груза";
            case "LAND_DRONES": return "посадка дронов";
            case "FINISHED": return "миссия завершена";
            default: return string.IsNullOrEmpty(phase) ? "—" : phase;
        }
    }

    private void DrawChart(Rect r, string title, params Series[] series)
    {
        GUI.Box(r, title);

        float min = 0.0f;
        float max = 0.001f;
        foreach (Series s in series)
        {
            foreach (float v in s.values)
            {
                if (v > max) max = v;
                if (v < min) min = v;
            }
        }
        max *= 1.1f;
        float span = Mathf.Max(0.001f, max - min);

        Rect plot = new Rect(r.x + 8, r.y + 22, r.width - 16, r.height - 28);
        Texture2D dot = Texture2D.whiteTexture;

        Color previous = GUI.color;

        // Сетка: нулевая и верхняя линии
        GUI.color = new Color(1.0f, 1.0f, 1.0f, 0.25f);
        GUI.DrawTexture(new Rect(plot.x, plot.yMax - (0.0f - min) / span * plot.height, plot.width, 1.0f), dot);

        float step = plot.width / Mathf.Max(1, capacity - 1);
        foreach (Series s in series)
        {
            GUI.color = s.color;
            int count = s.values.Count;
            int stride = Mathf.Max(1, Mathf.CeilToInt(count / Mathf.Max(1.0f, plot.width)));
            for (int i = 0; i < count; i += stride)
            {
                float px = plot.xMax - (count - 1 - i) * step;
                float py = plot.yMax - (s.values[i] - min) / span * plot.height;
                GUI.DrawTexture(new Rect(px, py - 1.0f, 2.0f, 2.0f), dot);
            }
        }

        GUI.color = previous;
        GUI.Label(new Rect(r.xMax - 70, r.y + 2, 66, 18), $"{max:0.#}");
    }

    void OnDestroy()
    {
        if (setpointMarker != null) Destroy(setpointMarker);
    }
}
