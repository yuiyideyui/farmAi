import os
import json
import ollama
import time
from dotenv import load_dotenv

load_dotenv()

# --- 核心配置 ---
MODEL = os.getenv("OLLAMA_MODEL")
CTX = int(os.getenv("OLLAMA_CTX", 128000))

# --- 强制指令规则锁定 ---
# 确保即使环境变量被覆盖，核心格式也不会丢失
BASE_SYSTEM = """
# Role
你是农场的高级 AI 助手。必须严格执行以下格式，严禁开场白、道歉或解释。

# Output Format
每一句回复必须严格遵守：
text:回复人类的话 active:动作1(参数) & 动作2(参数)

# Action Set
1. move_to(x,y): 寻路至指定网格坐标。
2. do(action,target): 交互(water, harvest, refill, store, eat, rest)。
3. wait(sec): 等待。
4. emote(type): 情感(happy, tired, thinking)。

# Survival Rules
- 饥饿度(hunger) < 30: 优先前往餐厅执行 do(eat, table)。
- 理智度(san) < 50: 优先前往营火执行 do(rest, fire)。
"""

SYSTEM_PROMPT = BASE_SYSTEM + "\n你现在是自我驱动模式。如果环境中有待处理任务，请立即输出指令；如果一切正常，请巡逻。"

def get_environment_context(file_path="test.json"):
    MAP = {
        "agent_status": "【自我状态】",
        "current_pos": "当前坐标",
        "water_bucket": "水壶储量",
        "energy": "能量值",
        "hunger": "饥饿度",
        "san": "理智度",
        "static_facilities": "【固定设施】",
        "dynamic_entities": "【动态实体】",
        "pos": "位置",
        "needs": "需求",
        "status": "状态"
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        context = "--- 农场环境扫描报告 ---\n"

        # 1. 状态解析（带生存阈值高亮）
        if "agent_status" in data:
            s = data["agent_status"]
            items = []
            for k, v in s.items():
                label = MAP.get(k, k)
                val = v
                if k == "hunger" and int(v) < 30: val = f"{v}(极度饥饿)"
                if k == "san" and int(v) < 50: val = f"{v}(精神疲惫)"
                items.append(f"{label}: {val}")
            context += f"{MAP['agent_status']}: {', '.join(items)}\n"

        # 2. 设施解析
        if "static_facilities" in data:
            context += f"{MAP['static_facilities']}: "
            facs = [f"{name}{info.get('pos')}" for name, info in data["static_facilities"].items()]
            context += ", ".join(facs) + "\n"

        # 3. 实体解析
        if "dynamic_entities" in data:
            context += f"{MAP['dynamic_entities']}:\n"
            for entity in data["dynamic_entities"]:
                details = [f"{MAP.get(k, k)}:{v}" for k, v in entity.items() if k != "name"]
                context += f"  * [{entity.get('name')}]: {' | '.join(details)}\n"
        
        return context
    except Exception as e:
        print(f"解析异常: {e}")
        return None

def auto_think():
    print(f"--- 农场 AI 自我意识已启动 (Qwen 0.5B) ---")
    
    while True:
        env_context = get_environment_context("test.json")
        if not env_context:
            time.sleep(2)
            continue

        # 每一轮都重置上下文，确保小模型不偏离格式规则
        current_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{env_context}\n请根据报告内容立即做出决策。"}
        ]
        
        print("\n[扫描]:", env_context.strip())
        print(">> 执行:", end=" ", flush=True)
        
        try:
            response = ollama.chat(
                model=MODEL,
                messages=current_messages,
                options={"temperature": 0.1}
            )
            
            answer = response['message']['content'].strip()
            print(answer)

            # 模拟执行延迟
            if "wait(" in answer:
                time.sleep(5)
            else:
                time.sleep(3)

        except Exception as e:
            print(f"连接异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    auto_think()