"""Python mirrors of the C# uDTP topic structs (Assets/Scripts/uDTP/Topics)."""

from RSMA.uDTP.Topics.ActuatorInputs import ActuatorInputs
from RSMA.uDTP.Topics.ArmCommand import ArmCommand
from RSMA.uDTP.Topics.CameraFramePacket import CameraFramePacket
from RSMA.uDTP.Topics.ControlLease import ControlLease
from RSMA.uDTP.Topics.FlightModeCommand import FlightModeCommand
from RSMA.uDTP.Topics.Float32 import Float32
from RSMA.uDTP.Topics.HILGPS import HILGPS
from RSMA.uDTP.Topics.HILOpticalFlow import HILOpticalFlow
from RSMA.uDTP.Topics.HILSensor import HILSensor
from RSMA.uDTP.Topics.HILStateQuaternion import HILStateQuaternion
from RSMA.uDTP.Topics.LaserScan128 import LaserScan128
from RSMA.uDTP.Topics.LaserScan256 import LaserScan256
from RSMA.uDTP.Topics.MotorInput import MotorInput
from RSMA.uDTP.Topics.Pose import Pose
from RSMA.uDTP.Topics.RCChannelsInput import RCChannelsInput
from RSMA.uDTP.Topics.RobotVelocity import RobotVelocity
from RSMA.uDTP.Topics.TrajectoryPoint import TrajectoryPoint

TOPIC_TYPES: dict[str, type] = {
    "ActuatorInputs": ActuatorInputs,
    "ArmCommand": ArmCommand,
    "CameraFramePacket": CameraFramePacket,
    "ControlLease": ControlLease,
    "FlightModeCommand": FlightModeCommand,
    "Float32": Float32,
    "HILGPS": HILGPS,
    "HILOpticalFlow": HILOpticalFlow,
    "HILSensor": HILSensor,
    "HILStateQuaternion": HILStateQuaternion,
    "LaserScan128": LaserScan128,
    "LaserScan256": LaserScan256,
    "MotorInput": MotorInput,
    "Pose": Pose,
    "RCChannelsInput": RCChannelsInput,
    "RobotVelocity": RobotVelocity,
    "TrajectoryPoint": TrajectoryPoint,
}

__all__ = ["TOPIC_TYPES", "ActuatorInputs", "ArmCommand", "CameraFramePacket", "ControlLease", "FlightModeCommand", "Float32", "HILGPS", "HILOpticalFlow", "HILSensor", "HILStateQuaternion", "LaserScan128", "LaserScan256", "MotorInput", "Pose", "RCChannelsInput", "RobotVelocity", "TrajectoryPoint"]
