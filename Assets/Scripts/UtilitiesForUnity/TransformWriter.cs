using UnityEngine;
using System.IO;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Implements the recording of formatted data in a csv file
/// </summary>
public class TransformWriter : MonoBehaviour
{
    public string fileName;
    public SuspensionDraw chart;
    public List<WritableTransform> targetTransforms = new List<WritableTransform>();

    public bool isWriting = false;

    public float timestep = 0.01f;

    [ContextMenu("Start writing")]
    public void Write()
    {
        if (isWriting) return;

        string path = Application.dataPath + "/" + fileName + ".csv";

        if (!File.Exists(path))
        {
            string header = "";

            foreach (WritableTransform target in targetTransforms)
            {
                header += $"{target.name};x;y;z;time;";
            }

            TextWriter textWriter = new StreamWriter(path, true);

            textWriter.WriteLine(header);

            textWriter.Close();
        }

        isWriting = true;
        StartCoroutine("WriteTransforms");
    }
    [ContextMenu("Stop writing")]
    public void Stop()
    {
        // Корутина сама завершит цикл и закроет файл; StopCoroutine оставлял файл незакрытым
        isWriting = false;
    }

    public IEnumerator WriteTransforms()
    {
        float time = 0f;

        string path = Application.dataPath + "/" + fileName + ".csv";

        TextWriter textWriter = new StreamWriter(path, true);

        while (isWriting)
        {
            string line = "";
            foreach (WritableTransform target in targetTransforms)
            {
                line += $";{target.transform.position.x};{target.transform.position.y};{target.transform.position.z};{time};";
                if (chart != null)
                    chart.UpdateChart(target.transform.position.y, time);
            }

            textWriter.WriteLine(line);

            time += timestep;
            yield return new WaitForSeconds(timestep);
        }

        Debug.Log("Done");
        textWriter.Close();
    }

    [Serializable]
    public struct WritableTransform
    {
        public string name;
        public Transform transform;
    }
}
