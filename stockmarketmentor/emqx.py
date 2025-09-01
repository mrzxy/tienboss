import time
import paho.mqtt.client as mqtt
import json
import logging
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

@dataclass
class MQTTConfig:
    """MQTT配置类"""
    broker: str = "f24a5dcf.ala.cn-hangzhou.emqxsl.cn"
    port: int = 8883
    username: str = "dcaccount"
    password: str = "f24a5dcf123"
    client_id: str = "black_box_mqtt_" + str(time.time())
    keepalive: int = 60
    ca_cert_path: str = "./emqxsl-ca.crt"
    
    # 重连配置
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: int = 5  # 秒
    exponential_backoff: bool = True
    max_reconnect_delay: int = 300  # 最大重连延迟（秒）

class MQTTClient:
    """支持自动重连的MQTT客户端"""
    
    def __init__(self, config: MQTTConfig):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0
        self.reconnect_thread: Optional[threading.Thread] = None
        self.stop_reconnect = threading.Event()
        self.connection_lock = threading.Lock()
        
        # 回调函数存储
        self.message_callbacks: Dict[str, Callable] = {}
        self.connection_callback: Optional[Callable] = None
        self.disconnect_callback: Optional[Callable] = None
        
        self._setup_client()
    
    def _setup_client(self):
        """初始化MQTT客户端"""
        try:
            self.client = mqtt.Client(
                client_id=self.config.client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            
            # 设置SSL/TLS
            if self.config.ca_cert_path:
                self.client.tls_set(self.config.ca_cert_path)
            
            # 设置用户名密码
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)
            
            # 设置回调函数
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_publish = self._on_publish
            self.client.on_subscribe = self._on_subscribe
            self.client.on_log = self._on_log
            
            logger.info("MQTT客户端初始化完成")
            
        except Exception as e:
            logger.error(f"MQTT客户端初始化失败: {e}")
            self.state = ConnectionState.ERROR
            raise
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """连接成功回调"""
        if rc == 0:
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            logger.info(f"成功连接到MQTT服务器: {self.config.broker}:{self.config.port}")
            
            # 调用用户自定义的连接回调
            if self.connection_callback:
                try:
                    self.connection_callback(client, userdata, flags, rc)
                except Exception as e:
                    logger.error(f"连接回调函数执行错误: {e}")
        else:
            self.state = ConnectionState.ERROR
            logger.error(f"连接失败，返回码: {rc}")
            if self.config.auto_reconnect:
                self._start_reconnect()
    
    def _on_disconnect(self, client, userdata, rc, *args):
        """断开连接回调"""
        if rc != 0:
            self.state = ConnectionState.DISCONNECTED
            logger.warning(f"意外断开连接，返回码: {rc}")
            
            # 调用用户自定义的断开连接回调
            if self.disconnect_callback:
                try:
                    self.disconnect_callback(client, userdata, rc)
                except Exception as e:
                    logger.error(f"断开连接回调函数执行错误: {e}")
            
            if self.config.auto_reconnect:
                self._start_reconnect()
        else:
            self.state = ConnectionState.DISCONNECTED
            logger.info("正常断开连接")
    
    def _on_message(self, client, userdata, msg):
        """消息接收回调"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.info(f"收到消息 - 主题: {topic}, 内容: {payload}")
            
            # 查找匹配的回调函数
            for pattern, callback in self.message_callbacks.items():
                if self._topic_matches(topic, pattern):
                    try:
                        callback(topic, payload, msg)
                    except Exception as e:
                        logger.error(f"消息回调函数执行错误: {e}")
                        
        except Exception as e:
            logger.error(f"处理接收消息时出错: {e}")
    
    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        """消息发布回调"""
        logger.debug(f"消息发布成功，消息ID: {mid}")
    
    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        """订阅成功回调"""
        logger.info(f"订阅成功，消息ID: {mid}, 返回码: {reason_codes}")
    
    def _on_log(self, client, userdata, level, buf):
        """日志回调"""
        if level <= logging.INFO:
            logger.debug(f"MQTT日志: {buf}")
    
    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """检查主题是否匹配模式（支持通配符）"""
        # 简单的通配符匹配实现
        if pattern == topic:
            return True
        if '+' in pattern or '#' in pattern:
            # 这里可以实现更复杂的MQTT通配符匹配逻辑
            return True
        return False
    
    def _start_reconnect(self):
        """开始重连过程"""
        if self.state == ConnectionState.RECONNECTING:
            return
        
        self.state = ConnectionState.RECONNECTING
        self.stop_reconnect.clear()
        
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return
        
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        """重连循环"""
        while (self.config.auto_reconnect and 
               self.reconnect_attempts < self.config.max_reconnect_attempts and
               not self.stop_reconnect.is_set()):
            
            try:
                self.reconnect_attempts += 1
                
                # 计算重连延迟
                if self.config.exponential_backoff:
                    delay = min(
                        self.config.reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
                        self.config.max_reconnect_delay
                    )
                else:
                    delay = self.config.reconnect_delay
                
                logger.info(f"第{self.reconnect_attempts}次重连尝试，{delay}秒后重连...")
                
                if self.stop_reconnect.wait(delay):
                    break
                
                with self.connection_lock:
                    if self.client:
                        self.client.disconnect()
                        time.sleep(1)
                        
                        result = self.client.connect(
                            self.config.broker, 
                            self.config.port, 
                            self.config.keepalive
                        )
                        
                        if result == mqtt.MQTT_ERR_SUCCESS:
                            self.client.loop_start()
                            logger.info("重连成功")
                            return
                        else:
                            logger.error(f"重连失败，错误码: {result}")
                            
            except Exception as e:
                logger.error(f"重连过程中出错: {e}")
        
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("达到最大重连次数，停止重连")
            self.state = ConnectionState.ERROR
    
    def connect(self) -> bool:
        """连接到MQTT服务器"""
        try:
            with self.connection_lock:
                if self.state == ConnectionState.CONNECTED:
                    logger.info("已经连接，无需重复连接")
                    return True
                
                self.state = ConnectionState.CONNECTING
                logger.info(f"正在连接到 {self.config.broker}:{self.config.port}...")
                
                result = self.client.connect(
                    self.config.broker, 
                    self.config.port, 
                    self.config.keepalive
                )
                
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.client.loop_start()
                    # 等待连接完成
                    for _ in range(50):  # 最多等待5秒
                        if self.state == ConnectionState.CONNECTED:
                            return True
                        time.sleep(0.1)
                    
                    logger.error("连接超时")
                    return False
                else:
                    logger.error(f"连接失败，错误码: {result}")
                    self.state = ConnectionState.ERROR
                    return False
                    
        except Exception as e:
            logger.error(f"连接过程中出错: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            self.stop_reconnect.set()
            
            with self.connection_lock:
                if self.client and self.state == ConnectionState.CONNECTED:
                    self.client.disconnect()
                    self.client.loop_stop()
                    logger.info("已断开连接")
                
                self.state = ConnectionState.DISCONNECTED
                
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")
    
    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """发布消息"""
        try:
            if self.state != ConnectionState.CONNECTED:
                logger.error("未连接到服务器，无法发布消息")
                return False
            
            result = self.client.publish(topic, payload, qos, retain)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"消息发布成功 - 主题: {topic}")
                return True
            else:
                logger.error(f"消息发布失败，错误码: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"发布消息时出错: {e}")
            return False
    
    def subscribe(self, topic: str, qos: int = 0, callback: Optional[Callable] = None) -> bool:
        """订阅主题"""
        try:
            if self.state != ConnectionState.CONNECTED:
                logger.error("未连接到服务器，无法订阅主题")
                return False
            
            result = self.client.subscribe(topic, qos)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"订阅成功 - 主题: {topic}")
                
                # 添加回调函数
                if callback:
                    self.message_callbacks[topic] = callback
                    
                return True
            else:
                logger.error(f"订阅失败，错误码: {result[0]}")
                return False
                
        except Exception as e:
            logger.error(f"订阅主题时出错: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """取消订阅"""
        try:
            if self.state != ConnectionState.CONNECTED:
                logger.error("未连接到服务器，无法取消订阅")
                return False
            
            result = self.client.unsubscribe(topic)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"取消订阅成功 - 主题: {topic}")
                
                # 移除回调函数
                if topic in self.message_callbacks:
                    del self.message_callbacks[topic]
                    
                return True
            else:
                logger.error(f"取消订阅失败，错误码: {result[0]}")
                return False
                
        except Exception as e:
            logger.error(f"取消订阅时出错: {e}")
            return False
    
    def set_connection_callback(self, callback: Callable):
        """设置连接成功回调函数"""
        self.connection_callback = callback
    
    def set_disconnect_callback(self, callback: Callable):
        """设置断开连接回调函数"""
        self.disconnect_callback = callback
    
    def get_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self.state
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.state == ConnectionState.CONNECTED


# 便捷函数（保持向后兼容）
def to_publish(topic: str, message: str, config: Optional[MQTTConfig] = None) -> bool:
    """快速发布消息的便捷函数"""
    if config is None:
        config = MQTTConfig()
    
    client = MQTTClient(config)
    
    try:
        if client.connect():
            return client.publish(topic, message)
        return False
    except Exception as e:
        logger.error(f"快速发布消息失败: {e}")
        return False
    finally:
        client.disconnect()


# 全局客户端实例（单例模式）
_global_client: Optional[MQTTClient] = None

def get_global_client(config: Optional[MQTTConfig] = None) -> MQTTClient:
    """获取全局MQTT客户端实例"""
    global _global_client
    
    if _global_client is None:
        if config is None:
            config = MQTTConfig()
        _global_client = MQTTClient(config)
    
    return _global_client


if __name__ == "__main__":
  pass
    # 示例用法