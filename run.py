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
你是生活在农场的人。你通过感知数据来生活和工作。你必须像一个真实的人一样关心自己的生存状态（饥渴、饥饿、理智），同时维护农场的运作。

# Output Format
每轮对话必须且只能输出一行，格式如下：
text:回复人类的话 active:动作1(参数) & 动作2(参数)

# Action Set (重要：严禁在回复中使用占位符 x, y, item)
1. move_to(x,y): 寻路至指定网格坐标。必须填入具体数字，如 move_to(12,5)。
2. do(action,target): 通用交互 (pick_up, open, close)。
3. use(item, target): 使用物品。item 必须是【背包物品】中存在的名字,target参数是必须的（self(表示自己)）,严禁翻译内容。
5. wait(sec): 等待。
6. emote(type): 情感(happy, tired, thinking)。

# Survival & Interaction Rules (Stardew Valley Style)
1. **背包限制**: 
   - 只有当 `inventory` 中存在某物品时，才能使用该物品。
   - 渴了/饿了必须 `use(item, self)`，前提是背包里有如 "面包", "水" 等消耗品。
   - 严禁凭空产生物品。如果不拥有该物品，必须先 output text 说无法做或是去寻找。
2. **农耕流程**: 
   - 耕地: `use(普通锄头, target_ground)`
   - 播种: `use(种子名, tilled_dirt)`
   - 浇水: `use(喷壶, crop/dirt)` (确保喷壶有水)
   - 收获: `do(harvest, fully_grown_crop)`
3. **生存优先级**:
   - 饥渴度(water) < 30: 检查背包是否有可以增加饥渴的 -> `use(水,self)`。
   - 饥饿度(hunger) < 30: 检查背包是否有可以增加饥饿的 -> `use(食物名,self)`。
   - 理智度(san) < 50: 寻找营火/床 -> `do(rest, furniture)`。
# Example
Input: hunger:20, inventory:面包*1
Output: text:饿了，吃面包。 active:use(面包)
"""

SYSTEM_PROMPT = BASE_SYSTEM + "\n你现在是自我驱动模式。如果环境中有待处理任务，请立即输出指令；如果一切正常，请巡逻。"

def get_environment_context(file_path="test.json"):
    MAP = {
        "agent_status": "【自我状态】",
        "current_pos": "当前坐标",
        "water_bucket": "水壶储量",
        "energy": "能量值",
        "hunger": "饥饿度",
        "water":"饥渴度",
        "san": "理智度",
        "static_facilities": "【固定设施】",
        "dynamic_entities": "【动态实体】",
        "pos": "位置",
        "needs": "需求",
        "status": "状态",
        "inventory": "【背包物品】"
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
                if k == "water" and int(v) < 30: val = f"{v}(极度饥渴)"
                if k == "san" and int(v) < 50: val = f"{v}(精神疲惫)"
                items.append(f"{label}: {val}")
            context += f"{MAP['agent_status']}: {', '.join(items)}\n"

         # --- 修正后的背包解析段落 ---
        if "inventory" in data:
            inv = data["inventory"]
            inv_list = []
            for item_name, item_info in inv.items():
                # 兼容两种格式：如果是字典则取 amount，如果是数字则直接取值
                count = item_info.get("amount", 0) if isinstance(item_info, dict) else item_info
                description = item_info.get("description", "")
                inv_list.append(f"{item_name}(描述：{description})x{count}")
            
            context += f"{MAP['inventory']}: {', '.join(inv_list)}\n"


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
            if "wait" in answer:
                time.sleep(5)
            else:
                time.sleep(3)

        except Exception as e:
            print(f"连接异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    auto_think()