using RSMA.uDTP;
using System;
using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class Quadrocopter : MonoBehaviour
{
    public int droneId;

    [Header("Физика и PID-регулятор")]
    public float maxSpeed = 8.0f;
    public float maxForce = 250.0f;
    public float positionKp = 8.0f;
    public float positionKi = 2.0f;
    public float positionKd = 2.0f;
    [Tooltip("Ограничение вклада интегральной составляющей, Н (защита от накопления ошибки)")]
    public float maxIntegralForce = 250.0f;

    [Header("Масса и сопротивление")]
    public float droneMass = 2.5f;      // Масса дрона из config.py
    public float linearDrag = 0.8f;
    public float angularDrag = 3.0f;

    [Header("Сглаживание цели")]
    [Tooltip("Вести цель к точке Python с ограничением скорости (maxSpeed) и ускорения (maxAcceleration): меньше раскачка груза")]
    public bool smoothTarget = false;
    public float maxAcceleration = 0.5f;

    [Header("Отказ")]
    [Tooltip("Имитация отказа: дрон перестает создавать тягу (для проверки отказоустойчивости)")]
    public bool isFailed = false;

    public GameObject propeller1 = null;
    public GameObject propeller2 = null;
    public GameObject propeller3 = null;
    public GameObject propeller4 = null;

    private float propMaxVelocity = 9800.0f;

    private Rigidbody rb;
    private Vector3 targetPosition;     // точка, заданная Python
    private Vector3 setpoint;           // точка, которую отрабатывает PID (с учетом сглаживания)
    private Vector3 setpointVelocity;
    private bool isControlledByApi = false;

    private Vector3 integralError = new Vector3(0, 0, 0);
    

    private RSMA.uDTP.Topics.Pose pose;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        rb.mass = droneMass;

#if UNITY_2023_1_OR_NEWER
        rb.linearDamping = linearDrag;
        rb.angularDamping = angularDrag;
#else
        rb.drag = linearDrag;
        rb.angularDrag = angularDrag;
#endif
        rb.useGravity = true;
    }

    private void Start()
    {
        pose = new RSMA.uDTP.Topics.Pose();
        pose.position = transform.position;
        pose.rotation = transform.rotation;
        pose.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

        targetPosition = transform.position;
        setpoint = transform.position;
        DataBroker.Publish($"DronePose_{droneId}", pose);
    }

    private void Update()
    {
        // 1. Публикуем текущую телеметрию в RSMA Broker
        pose.position = transform.position;
        pose.rotation = transform.rotation;
        pose.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

        DataBroker.Publish($"DronePose_{droneId}", pose);

        // 2. Безопасное получение целевой позиции из Python
        var targetPoseMsg = DataBroker.GetState<RSMA.uDTP.Topics.Pose>($"DroneTargetPose_{droneId}");

        if (targetPoseMsg.position != null)
        {
            // Убеждаемся, что координаты не нулевые
            if (targetPoseMsg.position != Vector3.zero)
            {
                SetTargetPosition(targetPoseMsg.position);
            }
        }
    }

    public void SetTargetPosition(Vector3 targetPos)
    {
        if (!isControlledByApi)
        {
            // Первая команда: сглаженная цель стартует из текущего положения
            setpoint = transform.position;
            setpointVelocity = Vector3.zero;
        }
        targetPosition = targetPos;
        isControlledByApi = true;
    }

    // Ведет setpoint к targetPosition с ограничением скорости и ускорения и торможением перед точкой
    private void UpdateSetpoint(float dt)
    {
        if (!smoothTarget || maxSpeed <= 0.0f)
        {
            setpoint = targetPosition;
            setpointVelocity = Vector3.zero;
            return;
        }

        Vector3 toTarget = targetPosition - setpoint;
        float distance = toTarget.magnitude;

        float speedLimit = maxSpeed;
        if (maxAcceleration > 0.0f)
            speedLimit = Mathf.Min(maxSpeed, Mathf.Sqrt(2.0f * maxAcceleration * distance));

        Vector3 desiredVelocity = distance > 1e-4f ? toTarget / distance * speedLimit : Vector3.zero;
        Vector3 deltaV = desiredVelocity - setpointVelocity;
        if (maxAcceleration > 0.0f)
            deltaV = Vector3.ClampMagnitude(deltaV, maxAcceleration * dt);
        setpointVelocity += deltaV;

        Vector3 step = setpointVelocity * dt;
        setpoint = step.magnitude >= distance ? targetPosition : setpoint + step;
    }

    void FixedUpdate()
    {
        if (!isControlledByApi || isFailed) return;

        UpdateSetpoint(Time.fixedDeltaTime);

        // Расчет ошибки позиции
        Vector3 positionError = setpoint - transform.position;
        integralError += positionError * Time.fixedDeltaTime;

        // Анти-windup: интегральная составляющая не больше maxIntegralForce
        if (positionKi > 0.0f)
            integralError = Vector3.ClampMagnitude(integralError * positionKi, maxIntegralForce) / positionKi;

        Vector3 currentVel = rb.linearVelocity;


        Vector3 force = (positionError * positionKp) + (integralError * positionKi) - (currentVel * positionKd);

        // Полная компенсация гравитации дрона
        force += -Physics.gravity * rb.mass;

        // Ограничение силы (до maxForce на дрон) с приоритетом вертикали:
        // горизонтальная составляющая получает только остаток, чтобы дрон не проседал при маневре
        float verticalForce = Mathf.Clamp(force.y, -maxForce, maxForce);
        Vector3 horizontalForce = new Vector3(force.x, 0.0f, force.z);
        float horizontalLimit = Mathf.Sqrt(maxForce * maxForce - verticalForce * verticalForce);
        horizontalForce = Vector3.ClampMagnitude(horizontalForce, horizontalLimit);
        force = horizontalForce + Vector3.up * verticalForce;

        rb.AddForce(force, ForceMode.Force);

        // Плавный поворот корпуса дрона по направлению движения (Visual Only)
        Vector3 horizontalError = new Vector3(positionError.x, 0, positionError.z);
        if (horizontalError.sqrMagnitude > 0.05f)
        {
            Quaternion targetRotation = Quaternion.LookRotation(horizontalError.normalized);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.fixedDeltaTime * 5.0f);
        }

        float propVelocity = propMaxVelocity * (force.magnitude / maxForce);

        propeller1.transform.Rotate(new Vector3(0, 0, -propVelocity) * Time.fixedDeltaTime);
        propeller2.transform.Rotate(new Vector3(0, 0, propVelocity) * Time.fixedDeltaTime);
        propeller3.transform.Rotate(new Vector3(0, 0, propVelocity) * Time.fixedDeltaTime);
        propeller4.transform.Rotate(new Vector3(0, 0, -propVelocity) * Time.fixedDeltaTime);
    }
}