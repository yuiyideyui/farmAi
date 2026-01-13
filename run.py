import os
import json
import ollama
import asyncio
import websockets
from dotenv import load_dotenv

# 加载配置
load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3")
CTX = int(os.getenv("OLLAMA_CTX", "4096"))

# --- 系统指令保持不变 ---
BASE_SYSTEM = """
你是一个生活在农场的 AI 行为体。
你通过扫描报告感知世界，只决定【下一步行动】。

【允许动作】

- move_to(x,y)：移动到网格坐标
- do()：对实体或区域执行交互,必须先移动到可交互的物体附近
- use(item,target)：使用背包物品,item必须是背包中存在的物品,target必须是环境中存在的实体例如自己是:self
- emote(type)：表达心情
- attack(sum)：攻击,sum是攻击的次数,例如攻击树打到树才可以获取木材,需要先移动到附近才可以攻击到附近目标

【行为优先级】
1. 身体含水量 < 30 → 优先喝水
2. 身体能量储备 < 30 → 优先进食
3. 状态正常 → 自由探索

【输出格式】
只能输出一行 JSON，可以多个动作：
{"thought": "思考过程", "text": "对玩家说的话", "actions": [{"type":"动作类型","x":0,"y":0,"target":"目标名"},{"type":"动作类型","x":0,"y":0,"target":"目标名"}]}
"""

# --- 核心逻辑：解析来自 Godot 的 JSON 数据 ---
def parse_environment(data):
    lines = ["--- 农场实时感知报告 ---"]
    
    # 玩家状态
    ps = data.get("player_status", {})
    pos = ps.get("pos", {})
    lines.append(f"【状态】坐标({pos.get('grid_x')},{pos.get('grid_y')}) 能量:{ps.get('nutrition')} 水:{ps.get('hydration')} 健康:{ps.get('health')}")
    
    # 背包
    inv = ps.get("inventory", {})
    items_str = ", ".join([f"{it.get('name')}({it.get('amount')})" for it in inv.get("items", [])])
    lines.append(f"【背包】{items_str if items_str else '空'}")

    # 实体
    for e in data.get("entities", []):
        gp = e.get("pixel_p", {})
        lines.append(f"【实体】{e.get('n')} 坐标({gp.get('x')},{gp.get('y')})宽高({e.get('w')},{e.get('h')}) 描述:{e.get('description')}")
        
    # ========== 地图层完整解析 ==========
    ml = data.get("map_layers", {})
    for layer_id, layer_data in ml.items():
        layer_desc = layer_data.get("description", "无描述")
        lines.append(f"【图层: {layer_id}】说明: {layer_desc}")
        
        areas = layer_data.get("areas", [])
        for i, area in enumerate(areas):
            # 1. 基础空间信息
            x, y = area.get("x", 0), area.get("y", 0)
            w, h = area.get("w", 1), area.get("h", 1)
            
            # 2. 动态提取功能属性 (过滤掉坐标和尺寸字段)
            features = []
            for key, value in area.items():
                if key not in ["x", "y", "w", "h"] and value == True:
                    features.append(f"属性:{key}")
            
            feature_str = f" [{', '.join(features)}]" if features else ""
            
            # 3. 组合成 AI 易读的行
            # 这里的格式告诉 AI：在哪个范围内 具有什么特性
            lines.append(
                f"  - 区域{i}: 范围({x},{y}) 到 ({x+w-1},{y+h-1}) 尺寸 {w}x{h}{feature_str}"
            )

    return "\n".join(lines)

# --- 处理 AI 思考 ---
async def ai_think(env_context):
    messages = [
        {"role": "system", "content": BASE_SYSTEM},
        {"role": "user", "content": f"{env_context}\n请决策。"}
    ]
    
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"temperature": 0.2, "num_ctx": CTX}
    )
    
    answer = response["message"]["content"].strip()
    if "{" in answer:
        answer = answer[answer.find("{"):answer.rfind("}")+1]
    return answer

# --- WebSocket 服务器核心 ---
async def handle_connection(websocket):
    print(f"\033[92m[连接]\033[0m Godot 客户端已接入")
    
    try:
        async for message in websocket:
            # 1. 接收来自 Godot 的 JSON
            try:
                raw_data = json.loads(message)
            except:
                print("解析 Godot 数据失败")
                continue

            # 2. 转换为文本上下文并打印
            env_context = parse_environment(raw_data)
            print("\n" + "="*40)
            print(env_context)

            # 3. AI 思考
            print(">> AI 思考中...")
            decision = await ai_think(env_context)
            print(f"\033[94m[决策]\033[0m: {decision}")

            # 4. 发回给 Godot
            await websocket.send(decision)
            
    except websockets.exceptions.ConnectionClosed:
        print("\033[91m[断开]\033[0m 客户端连接关闭")

async def main():
    server_ip = "127.0.0.1"
    server_port = 8765
    print(f"--- AI WebSocket 服务器已启动 ---")
    print(f"监听地址: ws://{server_ip}:{server_port}")
    
    async with websockets.serve(handle_connection, server_ip, server_port):
        await asyncio.Future()  # 永久运行

if __name__ == "__main__":
    asyncio.run(main())