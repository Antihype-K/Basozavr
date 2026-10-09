using UnityEngine;

/// <summary>
/// Камера сопровождения роя: плавно следует за грузом и держит его в кадре.
/// Назначается в рантайме из RSMASwarmEnvironment.
/// </summary>
public class SwarmFollowCamera : MonoBehaviour
{
    public Transform target;

    [Header("Позиция относительно груза")]
    public Vector3 offset = new Vector3(-9.0f, 7.0f, -9.0f);

    [Header("Плавность")]
    public float positionSmoothTime = 0.6f;
    public float rotationSpeed = 2.5f;

    // Точка прицеливания чуть выше груза, чтобы дроны и тросы попадали в кадр
    public float lookAtHeight = 1.5f;

    private Vector3 velocity = Vector3.zero;

    void LateUpdate()
    {
        if (target == null) return;

        Vector3 desiredPos = target.position + offset;
        transform.position = Vector3.SmoothDamp(
            transform.position, desiredPos, ref velocity, positionSmoothTime);

        Vector3 lookAt = target.position + Vector3.up * lookAtHeight;
        Quaternion desiredRot = Quaternion.LookRotation(lookAt - transform.position);
        transform.rotation = Quaternion.Slerp(
            transform.rotation, desiredRot, Time.deltaTime * rotationSpeed);
    }
}
