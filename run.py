import os
import json
import ollama
import time
from dotenv import load_dotenv

# 加载配置
load_dotenv()

# --- 核心配置 ---
MODEL = os.getenv("OLLAMA_MODEL")
CTX = int(os.getenv("OLLAMA_CTX"))

# --- 强化版系统指令（更适合小模型 & Godot） ---
BASE_SYSTEM = """
你是一个生活在农场的 AI 行为体。
你通过扫描报告感知世界，只决定【下一步行动】。

【允许动作】
- move_to(x,y)
- do(target)
- use(item,target)
- emote(type)

【物品语义】
- meta.type == food → 可 use 进食（身体能量储备）
- meta.type == water → 可 use 饮水（身体含水量）
- meta.type == container 且 is_filled=false → 可在井边 do() 装水
- 工具类物品（如 axe）必须在背包中，才能对实体执行 do()

【生存规则】
- 身体能量储备 / 身体含水量：数值越大状态越好（100=满）
- <30：紧急
- 30~80：正常
- >80：状态极佳，禁止补给

【行为优先级（严格）】
1. 身体含水量 < 30 → 喝水 / 去井边取水
2. 身体能量储备 < 30 → 吃食物
3. 状态正常或极佳 → 优先生产行为（砍树 / 种地）
4. 无可执行目标 → 巡逻移动

【交互规则】
- 只能对 interactive=true 的目标 do()
- do/use 前必须先 move_to
- 不允许编造物品或目标

【输出格式】
只能输出一行 JSON：
{
  "thought": "...",
  "text": "...",
  "actions": [
    {"type":"move_to","x":0,"y":0},
    {"type":"do","target":"对象名"}
  ]
}
"""


# --------------------------------------------------
def get_environment_context(file_path="test.json"):
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    lines.append("--- 农场实时感知报告 ---")

    # ========== 玩家状态 ==========
    ps = data.get("player_status", {})
    pos = ps.get("pos", {})
    lines.append(
        f"【玩家状态】"
        f" 坐标=({pos.get('grid_x',0)},{pos.get('grid_y',0)})"
        f" 身体能量储备={ps.get('nutrition',100)}/100"
        f" 身体含水量={ps.get('hydration',100)}/100"
        f" 生命={ps.get('health',100)}/100"
    )

    # ========== 背包 ==========
    inv = ps.get("inventory", {})
    lines.append(
        f"【背包】容量={inv.get('used',0)}/{inv.get('capacity',0)}"
    )

    for it in inv.get("items", []):
        lines.append(
            f" - 物品:"
            f" 名称={it.get('n')}"
            f" id={it.get('id')}"
            f" 数量={it.get('count',1)}"
            f" meta={it.get('meta',{})}"
        )

    # ========== 地图层 ==========
    for layer_name, areas in data.get("map_layers", {}).items():
        for a in areas:
            lines.append(
                f"【地图对象】"
                f" layer={layer_name}"
                f" t={a.get('t')}"
                f" 坐标=({a.get('x')},{a.get('y')})"
                f" 尺寸=({a.get('w',1)}x{a.get('h',1)})"
                f" nav={a.get('nav')}"
                f" interactive={a.get('interactive')}"
                f" 描述={a.get('description','')}"
            )

    # ========== 实体 ==========
    for e in data.get("entities", []):
        gp = e.get("grid_p", {})
        lines.append(
            f"【实体】"
            f" 名称={e.get('n')}"
            f" 坐标=({gp.get('x')},{gp.get('y')})"
            f" interactive={e.get('interactive')}"
            f" is_ready={e.get('is_ready')}"
            f" meta={e.get('meta',{})}"
            f" 描述={e.get('description','')}"
        )

    return "\n".join(lines)

# --------------------------------------------------

def is_valid_ai_output(text: str) -> bool:
    try:
        obj = json.loads(text)
        return isinstance(obj.get("actions"), list)
    except Exception:
        return False

# --------------------------------------------------

def auto_think():
    print("--- 农场 AI 决策引擎（原结构强化版）---")

    while True:
        env_context = get_environment_context("test.json")
        print(env_context)
        if not env_context:
            print(">> 等待 test.json ...")
            time.sleep(2)
            continue

        messages = [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": f"{env_context}\n请做出下一步行动决策。"}
        ]

        try:
            print("\n" + "=" * 50)
            print(">> AI 思考中...")

            response = ollama.chat(
                model=MODEL,
                messages=messages,
                options={
                    "temperature": 0.2,
                    "num_ctx": CTX
                }
            )

            answer = response["message"]["content"].strip().replace("\n", "")

            if not is_valid_ai_output(answer):
                print("[警告] AI 输出格式异常：", answer)
            else:
                print("\033[94m[AI 决策]\033[0m:", answer)

            print("\n" + "-" * 30)
            input(">>> 执行完成，回车进入下一轮")

        except Exception as e:
            print(f"[错误] Ollama 连接失败: {e}")
            time.sleep(5)

# --------------------------------------------------

if __name__ == "__main__":
    auto_think()
