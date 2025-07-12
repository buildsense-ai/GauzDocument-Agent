import base64
import httpx
import os
from dotenv import load_dotenv

class OpenRouterClient:
    def __init__(self, api_key=None):
        # 每次创建实例时重新加载环境变量，确保获取最新的API key
        load_dotenv(override=True)
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Please set the OPENROUTER_API_KEY environment variable.")
        
        self.api_base = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # VLM深度分析使用的模型
        self.vlm_model = "google/gemini-2.5-flash"

    def _encode_image(self, image_path):
        """Encodes an image to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def get_available_models(self):
        """
        获取OpenRouter上可用的模型列表
        
        Returns:
            List of available models
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.api_base}/models",
                    headers=self.headers
                )
                response.raise_for_status()
                result = response.json()
                return result.get('data', [])
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []
    
    def check_gemini_model(self):
        """
        检查Gemini 2.5 Flash模型是否可用
        
        Returns:
            bool: 模型是否可用
        """
        models = self.get_available_models()
        gemini_models = [m for m in models if 'gemini' in m.get('id', '').lower()]
        
        print(f"🔍 找到 {len(gemini_models)} 个Gemini模型:")
        for model in gemini_models:
            model_id = model.get('id', '')
            model_name = model.get('name', '')
            print(f"  - {model_id}: {model_name}")
            
        # 检查我们使用的模型是否存在
        target_model = self.vlm_model
        is_available = any(m.get('id') == target_model for m in models)
        
        if is_available:
            print(f"✅ 目标模型 {target_model} 可用")
        else:
            print(f"❌ 目标模型 {target_model} 不可用")
            
        return is_available

    def get_image_description_gemini(self, image_path: str, prompt: str) -> str:
        """
        Gets the description of an image using Gemini 2.5 Flash on OpenRouter.

        Args:
            image_path: The path to the image file.
            prompt: The prompt to use for the VLM.

        Returns:
            The description of the image.
        """
        base64_image = self._encode_image(image_path)
        
        payload = {
            "model": self.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2048,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                description = result['choices'][0]['message']['content']
                return description.strip()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return f"Error: Failed to get description from OpenRouter due to HTTP status error."
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return "Error: An unexpected error occurred while fetching the image description."

if __name__ == '__main__':
    # Example usage:
    # Make sure to have an OPENROUTER_API_KEY in your .env file
    # and an example image at 'example.png'
    if not os.path.exists('example.png'):
        print("Please create an 'example.png' file to test the client.")
    else:
        client = OpenRouterClient()
        prompt_text = """请作为专业的图像分析师，详细分析和描述这张图片的内容。请按以下结构回答：

1. 图像类型：确定这是照片、图表、工程图、技术图纸、流程图还是其他类型
2. 核心内容：描述图像的主要元素和信息
3. 技术细节：如果是技术图纸或图表，请详细解释其结构、数据、标注和关键信息
4. 文本内容：识别并转录图像中的所有可见文字、数字、标签
5. 空间布局：描述元素的位置关系和整体布局
6. 颜色和样式：描述主要颜色、线条样式、符号等视觉特征

请用中文回答，尽可能详细和准确。"""
        description = client.get_image_description_gemini('example.png', prompt=prompt_text)
        print("Image Description:")
        print(description) 