from openai import OpenAI
import os
from typing import List, Dict, Any, Optional, Generator, Union


class EnhancedOpenAI:
    # 不支持system prompt和temperature的模型列表
    NO_SYSTEM_PROMPT_MODELS = [
        "o1-mini",
        "o1-preview",
    ]
    NO_TEMPERATURE_MODELS = [
        "o1-mini",
        "o1-preview",
    ]
    
    def __init__(self, model_name: str, base_url: str = None, api_key: str = None):
        """
        初始化增强版OpenAI客户端
        
        Args:
            model_name: 模型名称
            base_url: API基础URL，可选，用于自定义API端点
            api_key: API密钥，可选，如不提供则从环境变量获取
        """
        self.model_name = model_name
        self.base_url = base_url
        
        # 优先使用传入的API密钥，否则尝试从环境变量获取
        self.api_key = api_key or os.getenv("ONEAPI_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API密钥未设置，请通过参数传入或设置环境变量 ONEAPI_KEY 或 OPENAI_API_KEY")
        
        # 初始化客户端
        client_args = {"api_key": self.api_key}
        if base_url:
            client_args["base_url"] = base_url
            
        try:
            self.client = OpenAI(**client_args)
        except Exception as e:
            raise ValueError(f"初始化OpenAI客户端失败: {str(e)}")
    
    def _supports_system_prompt(self) -> bool:
        """
        检查当前模型是否支持system prompt
        
        Returns:
            布尔值，表示是否支持system prompt
        """
        for model_prefix in self.NO_SYSTEM_PROMPT_MODELS:
            if self.model_name.startswith(model_prefix):
                return False
        return True
    
    def _supports_temperature(self) -> bool:
        """
        检查当前模型是否支持temperature参数
        
        Returns:
            布尔值，表示是否支持temperature参数
        """
        for model_prefix in self.NO_TEMPERATURE_MODELS:
            if self.model_name.startswith(model_prefix):
                return False
        return True
    
    def _prepare_messages(self, 
                          system_prompt: Optional[str] = None, 
                          user_message: str = None,
                          message_history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """
        准备消息列表，适配不同模型的需求
        
        Args:
            system_prompt: 系统提示，可选
            user_message: 用户消息
            message_history: 消息历史，可选
            
        Returns:
            消息列表
        """
        messages = message_history.copy() if message_history else []
        
        # 如果提供了系统提示
        if system_prompt:
            if self._supports_system_prompt():
                # 检查消息历史中是否已有系统提示
                if not any(msg.get("role") == "system" for msg in messages):
                    messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                # 对于不支持system prompt的模型，将system prompt添加到user_message前面
                if user_message:
                    user_message = f"{system_prompt}\n\n{user_message}"
        
        # 添加用户消息
        if user_message:
            messages.append({"role": "user", "content": user_message})
            
        return messages
    
    def chat(self, 
             user_message: str, 
             system_prompt: Optional[str] = None,
             message_history: Optional[List[Dict[str, str]]] = None,
             model_name: str = None,
             temperature: float = 0.1,
             max_tokens: Optional[int] = None,
             **kwargs) -> str:
        """
        发送聊天请求并获取回复
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示，可选
            message_history: 消息历史，可选
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数，可选
            **kwargs: 其他参数传递给OpenAI API
            
        Returns:
            模型回复文本
        """
        if model_name:
            self.model_name = model_name
        messages = self._prepare_messages(system_prompt, user_message, message_history)
        
        # 准备API调用参数
        api_params = {
            "model": self.model_name,
            "messages": messages,
        }
        
        # 仅当模型支持temperature时添加该参数
        if self._supports_temperature():
            api_params["temperature"] = temperature
        
        if max_tokens:
            api_params["max_tokens"] = max_tokens
            
        # 合并其他参数
        api_params.update(kwargs)
        
        try:
            response = self.client.chat.completions.create(**api_params)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"调用OpenAI API失败: {str(e)}")
    
    def stream_chat(self, 
                   user_message: str, 
                   system_prompt: Optional[str] = None,
                   message_history: Optional[List[Dict[str, str]]] = None,
                   model_name: str = None,
                   temperature: float = 0.1,
                   max_tokens: Optional[int] = None,
                   **kwargs) -> Generator[str, None, None]:
        """
        流式聊天，逐步返回模型生成的内容
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示，可选
            message_history: 消息历史，可选
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数，可选
            **kwargs: 其他参数传递给OpenAI API
            
        Yields:
            模型生成的文本片段
        """
        if model_name:
            self.model_name = model_name
        messages = self._prepare_messages(system_prompt, user_message, message_history)
        
        # 准备API调用参数
        api_params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        
        # 仅当模型支持temperature时添加该参数
        if self._supports_temperature():
            api_params["temperature"] = temperature
        
        if max_tokens:
            api_params["max_tokens"] = max_tokens
            
        # 合并其他参数
        api_params.update(kwargs)
        
        try:
            stream = self.client.chat.completions.create(**api_params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(f"流式调用OpenAI API失败: {str(e)}")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        try:
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",  # 可以根据需要修改嵌入模型
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"获取嵌入向量失败: {str(e)}") 
        

if __name__ == "__main__":
    print("--------------------------------")
    from dotenv import load_dotenv
    load_dotenv()
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_KEY")
    model_name = "o1-preview"
    openai = EnhancedOpenAI(model_name, base_url, api_key)
    print(openai.chat("你好"))
