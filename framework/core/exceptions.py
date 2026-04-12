class FrameworkError(Exception):
    """框架级异常基类。"""


class ConfigError(FrameworkError):
    """配置缺失或配置不合法时抛出。"""


class DeviceConnectionError(FrameworkError):
    """框架无法连接设备时抛出。"""


class ElementNotFoundError(FrameworkError):
    """定位器无法解析到目标元素时抛出。"""


class ImageMatchError(FrameworkError):
    """图像匹配失败或匹配分数过低时抛出。"""
