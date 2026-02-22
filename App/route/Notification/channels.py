from typing import Dict, List, Set
from fastapi import WebSocket, APIRouter, WebSocketDisconnect, logger
import logging
import asyncio
logger = logging.getLogger(__name__)
from fastapi import HTTPException
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

notification_router = APIRouter(prefix="/v1", tags=["Notification"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_uuid: str):
        await websocket.accept()
        if user_uuid not in self.active_connections:
            self.active_connections[user_uuid] = set()
        self.active_connections[user_uuid].add(websocket)

    def disconnect(self, websocket: WebSocket, user_uuid: str):
        self.active_connections[user_uuid].remove(websocket)
        if not self.active_connections[user_uuid]:
            del self.active_connections[user_uuid]

    async def send_personal_message(self, message: dict, user_uuid: str):
        print(message)
        logger.info(f"activeconnection:{self.active_connections}")
        if user_uuid in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[user_uuid]:
                try:
                    await connection.send_text(str(message))
                    logger.info(f"Message sent to user {user_uuid}")
                except RuntimeError as e:
                    logger.error(f"Error sending message to user {user_uuid}: {str(e)}")
                    disconnected.add(connection)

            # Remove disconnected websockets
            self.active_connections[user_uuid] -= disconnected
        else:
            logger.warning(f"No active connection for user {user_uuid}")

    async def broadcast(self, message: str):
        for connections in self.active_connections.values():
            for connection in connections:
                await connection.send_text(message)


manager = ConnectionManager()


@notification_router.websocket("/ws/{user_uuid}")
async def websocket_endpoint(websocket: WebSocket, user_uuid: str):
    await manager.connect(websocket, user_uuid)

    async def ping_task():
        try:
            while True:
                await asyncio.sleep(58)
                await websocket.send_text("ping")  # You can use JSON too if needed
        except Exception as e:
            logger.warning(f"Ping failed for user {user_uuid}: {e}")
            manager.disconnect(websocket, user_uuid)
            return error.error(f"{str(e)}", 500, "Ping failed")

    ping = asyncio.create_task(ping_task())

    try:
        while True:
            data = await websocket.receive_text()
            # You can respond to pings or client messages here
            logger.info(f"Received from {user_uuid}: {data}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_uuid}")
        ping.cancel()
        manager.disconnect(websocket, user_uuid)
    except Exception as e:
        logger.error(f"Error in websocket for user {user_uuid}: {e}")
        ping.cancel()
        manager.disconnect(websocket, user_uuid)
        return error.error(f"{str(e)}", 500, "WebSocket Error")
