"""
JSON-RPC 2.0 基础协议实现
"""

from typing import Optional, Dict, Any


class JSONRPCRequest:
    """JSON-RPC 2.0 请求对象"""
    
    def __init__(self, method: str, params: Optional[Dict] = None, request_id: Optional[str] = None):
        """
        初始化请求对象
        
        Args:
            method: 方法名（如 "status_update"）
            params: 参数字典
            request_id: 请求ID（可选）
        """
        self.jsonrpc = "2.0"
        self.method = method
        self.params = params or {}
        self.id = request_id
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params
        }
        if self.id:
            result["id"] = self.id
        return result
    
    def __repr__(self) -> str:
        return f"JSONRPCRequest(method='{self.method}', params={self.params}, id='{self.id}')"


class JSONRPCResponse:
    """JSON-RPC 2.0 响应对象"""
    
    def __init__(self, result: Optional[Dict] = None, error: Optional[Dict] = None, 
                 request_id: Optional[str] = None):
        """
        初始化响应对象
        
        Args:
            result: 结果数据
            error: 错误信息
            request_id: 对应的请求ID
        """
        self.jsonrpc = "2.0"
        self.result = result
        self.error = error
        self.id = request_id
        
        # 验证结果和错误不能同时存在
        if result is not None and error is not None:
            raise ValueError("结果和错误不能同时存在")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        response = {
            "jsonrpc": self.jsonrpc,
        }
        
        if self.error is not None:
            response["error"] = self.error
        else:
            response["result"] = self.result or {}
            
        if self.id:
            response["id"] = self.id
            
        return response
    
    def is_success(self) -> bool:
        """判断响应是否成功"""
        return self.error is None
    
    def is_error(self) -> bool:
        """判断响应是否错误"""
        return self.error is not None
    
    @classmethod
    def success(cls, result: Dict, request_id: Optional[str] = None) -> 'JSONRPCResponse':
        """创建成功响应"""
        return cls(result=result, request_id=request_id)
    
    @classmethod
    def error_response(cls, code: int, message: str, data: Optional[Dict] = None, 
                      request_id: Optional[str] = None) -> 'JSONRPCResponse':
        """创建错误响应"""
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data
        return cls(error=error, request_id=request_id)
    
    def __repr__(self) -> str:
        if self.is_success():
            return f"JSONRPCResponse(success, result={self.result}, id='{self.id}')"
        else:
            return f"JSONRPCResponse(error={self.error}, id='{self.id}')"


class JSONRPCNotification:
    """JSON-RPC 2.0 通知对象（无ID的请求）"""
    
    def __init__(self, method: str, params: Optional[Dict] = None):
        """
        初始化通知对象
        
        Args:
            method: 方法名
            params: 参数字典
        """
        self.jsonrpc = "2.0"
        self.method = method
        self.params = params or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params
        }
    
    def __repr__(self) -> str:
        return f"JSONRPCNotification(method='{self.method}', params={self.params})"