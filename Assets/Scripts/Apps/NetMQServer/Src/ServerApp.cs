using RSMA.NetMQ;
using UnityEngine;
using UnityEngine.UI;

namespace RSMA.GUI 
{
    public class ServerApp : Window
    {
        private GameObject _mainPannel = null;

        private Button _stateButton = null;
        private Text _stateText = null;
        private InputField _portInputField = null;

        // Порт можно задать переменной окружения RSMA_PORT (так делает автозапуск из Python)
        private static int DefaultPort
        {
            get
            {
                string fromEnv = System.Environment.GetEnvironmentVariable("RSMA_PORT");
                return int.TryParse(fromEnv, out int port) && port > 0 && port < 65536 ? port : 5555;
            }
        }

        void Awake()
        {
            DontDestroyOnLoad(gameObject);
            NetMQServer.Run(DefaultPort);
        }

        void Update()
        {
            NetMQServer.Update();
            RefreshState();
        }

        // Сервер может остановиться сам (например, порт занят), поэтому статус берется из NetMQServer
        private void RefreshState()
        {
            if (_stateText == null) return;

            bool running = NetMQServer.IsRunning;
            string text = running ? "Online" : "Offline";
            if (_stateText.text != text)
            {
                _stateText.text = text;
                _stateText.color = running ? Color.green : Color.red;
            }
        }

        void OnApplicationQuit()
        {
            NetMQServer.Stop();
        }

        public void SwitchState() 
        {
            if (NetMQServer.IsRunning) 
            {
                NetMQServer.Stop();
                Debug.Log("Stopping NetMQServer");
                RefreshState();
                return;
            }
            int port = DefaultPort;

            if (!int.TryParse(_portInputField.text, out port))
            {
                port = DefaultPort;
                _portInputField.text = port.ToString();
            }

            NetMQServer.Run(port);
            Debug.Log($"Running NetMQServer on {port}");
            RefreshState();
        }

        protected override void Start() 
        { 
            base.Start();

            _mainPannel = UIBuilder.CreatePanel("GridContainer", _transform);
            RectTransform rt = _mainPannel.GetComponent<RectTransform>();
            rt.anchorMin = new Vector2(0.1f, 0.1f);
            rt.anchorMax = new Vector2(0.9f, 0.9f);
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            var portLabel = UIBuilder.CreateLabel("Port label", _mainPannel.transform, "Port: ", font, 25);
            UIBuilder.PlaceInGrid(portLabel.gameObject, 0, 0, 1, 1, 3, 2);
            _portInputField = UIBuilder.CreateInputField("Port input", _mainPannel.transform, font, 25, DefaultPort.ToString());
            UIBuilder.PlaceInGrid(_portInputField.gameObject, 0, 1, 1, 1, 3, 2);
            _portInputField.text = DefaultPort.ToString();

            var stateLabel = UIBuilder.CreateLabel("State label", _mainPannel.transform, "Server state:", font, 25);
            UIBuilder.PlaceInGrid(stateLabel.gameObject, 1, 0, 1, 1, 3, 2);
            _stateText = UIBuilder.CreateLabel("State text", _mainPannel.transform, "Online", font, 25);
            _stateText.color = Color.green;
            UIBuilder.PlaceInGrid(_stateText.gameObject, 1, 1, 1, 1, 3, 2);

            _stateButton = UIBuilder.CreateButton("State button", _mainPannel.transform, "Enable/Disable", font, 25, SwitchState);
            UIBuilder.PlaceInGrid(_stateButton.gameObject, 2, 0, 1, 2, 3, 2);

            Close();
        }

        public override void Close()
        {
            base.Close();
            _mainPannel.SetActive(false);
        }

        public override void Open()
        {
            base.Open();
            _mainPannel.SetActive(true);
        }
    }
}

