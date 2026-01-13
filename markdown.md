# 判断要去的点是否在navigation内

```gd
func is_point_walkable(global_pos: Vector2) -> bool:
	# 1. 获取当前世界的导航地图 RID
	var map_rid = get_world_2d().get_navigation_map()

	# 2. 在导航网格上找到离 global_pos 最近的一个点
	var closest_point = NavigationServer2D.map_get_closest_point(map_rid, global_pos)

	# 3. 比较“原始点”和“最近点”的距离
	# 如果距离非常小（比如小于 1.0 像素），说明这个点就在导航多边形里面
	var distance = global_pos.distance_to(closest_point)

	return distance < 1.0 # 返回 true 表示可行走
```