from pydantic import BaseModel
from typing import List, Optional, Union
from enum import Enum
from pydantic import Field

class NodeType(str, Enum):
    CLIENT = "CLIENT"
    DEPOT = "DEPOT"
    INTERMEDIATE = "INTERMEDIATE"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"

class VehicleStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    IN_TRANSIT = "IN_TRANSIT"
    ASSIGNED = "ASSIGNED"
    OFFLINE = "OFFLINE"


class Node(BaseModel):
    id: Union[int, str]  # 👈 accetta sia "1" che 1
    name: str
    lat: float
    lon: float
    type: NodeType = Field(NodeType.CLIENT, alias="type")

    model_config = {
        "validate_by_name": True,
        "extra": "ignore"
    }

class Order(BaseModel):
    id: Union[int, str]
    pickup_node_id: Union[int, str] = Field(..., alias="pickupNodeId")
    delivery_node_id: Union[int, str] = Field(..., alias="deliveryNodeId")
    quantity: int
    tw_open: int = Field(..., alias="twOpen")
    tw_close: int = Field(..., alias="twClose")
    assigned_vehicle_id: Optional[str] = Field(None, alias="assignedVehicleId")
    status: Optional[OrderStatus] = Field(OrderStatus.PENDING, alias="status")

    model_config = {
        "validate_by_name": True,
        "extra": "ignore"
    }

class Vehicle(BaseModel):
    id: Union[int, str]
    plate: Optional[str] = None
    capacity: int
    cost: int
    current_lat: Optional[float] = Field(None, alias="currentLat")
    current_lon: Optional[float] = Field(None, alias="currentLon")
    status: Optional[VehicleStatus] = Field(VehicleStatus.AVAILABLE, alias="status")

    model_config = {
        "validate_by_name": True,
        "extra": "ignore"
    }

class OptimizeRequest(BaseModel):
    nodes: List[Node]
    orders: List[Order]
    vehicles: List[Vehicle]

    model_config = {
        "validate_by_name": True,
        "extra": "ignore"
    }