using UnityEngine;

/// <summary>
/// Определение высоты поверхности под точкой: сначала по рельефу (Terrain),
/// затем по любому коллайдеру ниже точки. Нужно, чтобы точки миссии ложились
/// на землю на сцене с рельефом, а не висели на нулевой высоте.
/// </summary>
public static class GroundProbe
{
    // Насколько приподнимать точку над найденной поверхностью, м
    public const float DefaultClearance = 0.15f;

    /// <summary>Возвращает точку с высотой по поверхности; XZ не меняются.</summary>
    public static Vector3 Resolve(Vector3 point, float clearance = DefaultClearance)
    {
        float groundY;
        if (TryTerrainHeight(point, out groundY))
        {
            return new Vector3(point.x, groundY + clearance, point.z);
        }

        RaycastHit hit;
        if (Physics.Raycast(point + Vector3.up * 300.0f, Vector3.down, out hit, 600.0f))
        {
            return new Vector3(point.x, hit.point.y + clearance, point.z);
        }

        return point;
    }

    /// <summary>Высота рельефа под точкой. false, если точка вне всех тайлов Terrain.</summary>
    public static bool TryTerrainHeight(Vector3 point, out float groundY)
    {
        groundY = 0.0f;

        Terrain[] terrains = Object.FindObjectsByType<Terrain>(FindObjectsSortMode.None);
        if (terrains == null || terrains.Length == 0) return false;

        bool found = false;
        foreach (Terrain t in terrains)
        {
            if (t.terrainData == null) continue;

            Vector3 local = point - t.transform.position;
            Vector3 size = t.terrainData.size;

            // Точка должна лежать в пределах этого тайла рельефа
            if (local.x < 0.0f || local.z < 0.0f || local.x > size.x || local.z > size.z) continue;

            float h = t.SampleHeight(point) + t.transform.position.y;
            if (!found || h > groundY)
            {
                groundY = h;
                found = true;
            }
        }

        return found;
    }
}
