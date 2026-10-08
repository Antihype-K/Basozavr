import zmq
import json
from dataclasses import dataclass, asdict, is_dataclass
from RSMA.Serializer import RSMASerializer

class RSMAClient:
    """Client for RSMA ZeroMQ server"""
    def __init__(self, host="localhost", port=5555, timeout: int = 5000):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)

        self.socket.setsockopt(zmq.RCVTIMEO, timeout)
        self.socket.setsockopt(zmq.SNDTIMEO, timeout)
        self.socket.connect(f"tcp://{host}:{port}")

    def send_command(self, raw_command: str) -> str:
        """Sends command to RSMA server"""
        try:
            self.socket.send_string(raw_command)
            return self.socket.recv_string()
        except zmq.error.Again:
            return "Error: Timeout waiting for response from Unity"

    def publish(self, topic_name: str, data_object: any):
        """
        Publishes data to topic via RSMA uDTP
        """
        dict_data = RSMASerializer.to_dict(data_object)

        packet = {
            "Action": "publish",
            "TopicName": topic_name,
            "TopicType": type(data_object).__name__.split('.')[-1],
            "Data": json.dumps(dict_data)
        }

        try:
            self.socket.send_string(json.dumps(packet))
            response_raw = self.socket.recv_string()
            return json.loads(response_raw)
        except zmq.error.Again:
            return {"status": "error", "message": "Timeout"}
        except json.JSONDecodeError:
            return {"status": "error", "message": f"Raw response error: {response_raw}"}

    def get_state(self, topic_name: str, target_class: type) -> any:
        """
        Gets data from topic via RSMA uDTP
        """
        packet = {
            "Action": "get",
            "TopicName": topic_name,
            "TopicType": target_class.__name__.split('.')[-1],
            "Data": ""
        }

        try:
            self.socket.send_string(json.dumps(packet))
            response_raw = self.socket.recv_string()
            response = json.loads(response_raw)
            
            status = response.get("Status") or response.get("status")
            data_content = response.get("Data") or response.get("data")

            if status == "ok" and data_content:
                parsed_json = json.loads(data_content)

                return RSMASerializer.from_dict(target_class, parsed_json)
                    
            return None
        except Exception as e:
            print(f"Error in get_state: {e}")
            return None

    def close(self):
        """Disconnects client"""
        self.socket.close()
        self.context.term()