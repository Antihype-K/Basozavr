using Newtonsoft.Json;
using System;
using UnityEngine;

namespace RSMA.NetMQ
{
    /// <summary>
    /// Vector3 как {"x","y","z"}. Без конвертера Newtonsoft сериализует все свойства структуры, включая normalized
    /// (который сам Vector3), и топики Pose уходят клиенту с рекурсивным вложением.
    /// </summary>
    public class Vector3JsonConverter : JsonConverter
    {
        public override bool CanConvert(Type objectType) => objectType == typeof(Vector3);

        public override void WriteJson(JsonWriter writer, object value, JsonSerializer serializer)
        {
            Vector3 v = (Vector3)value;
            writer.WriteStartObject();
            writer.WritePropertyName("x"); writer.WriteValue(v.x);
            writer.WritePropertyName("y"); writer.WriteValue(v.y);
            writer.WritePropertyName("z"); writer.WriteValue(v.z);
            writer.WriteEndObject();
        }

        public override object ReadJson(JsonReader reader, Type objectType, object existingValue, JsonSerializer serializer)
        {
            if (reader.TokenType == JsonToken.Null) return Vector3.zero;
            var o = Newtonsoft.Json.Linq.JObject.Load(reader);
            return new Vector3(o.Value<float?>("x") ?? 0.0f, o.Value<float?>("y") ?? 0.0f, o.Value<float?>("z") ?? 0.0f);
        }
    }

    /// <summary>Quaternion как {"x","y","z","w"}.</summary>
    public class QuaternionJsonConverter : JsonConverter
    {
        public override bool CanConvert(Type objectType) => objectType == typeof(Quaternion);

        public override void WriteJson(JsonWriter writer, object value, JsonSerializer serializer)
        {
            Quaternion q = (Quaternion)value;
            writer.WriteStartObject();
            writer.WritePropertyName("x"); writer.WriteValue(q.x);
            writer.WritePropertyName("y"); writer.WriteValue(q.y);
            writer.WritePropertyName("z"); writer.WriteValue(q.z);
            writer.WritePropertyName("w"); writer.WriteValue(q.w);
            writer.WriteEndObject();
        }

        public override object ReadJson(JsonReader reader, Type objectType, object existingValue, JsonSerializer serializer)
        {
            if (reader.TokenType == JsonToken.Null) return Quaternion.identity;
            var o = Newtonsoft.Json.Linq.JObject.Load(reader);
            return new Quaternion(o.Value<float?>("x") ?? 0.0f, o.Value<float?>("y") ?? 0.0f,
                                  o.Value<float?>("z") ?? 0.0f, o.Value<float?>("w") ?? 1.0f);
        }
    }
}
