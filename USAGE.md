# Agent3D 使用文档

基于多智能体协作与几何物理反馈的 Blender 程序化场景生成系统。

## 快速开始

```bash
# 修改 main.py 中的 user_request 变量
python main.py
```

系统会读取用户描述 → 确定性空间规划 → 生成 Blender 代码 → 后台运行 Blender 物理验证 → 如出错自动修正（最多4次迭代）。

输出文件：`outputs/final_scene.blend`

---

## 支持的物体类型 (36种)

### 平台型 (platform) — 可作为场景中心，其他物体围绕其排列

| 类型 | 英文名 | 中文别名 | 默认尺寸 (宽×深×高 m) | 几何类型 |
|------|--------|----------|----------------------|----------|
| 桌子 | table | 桌子, 餐桌, 书桌, 茶几 | 1.2×0.8×0.75 | composite |
| 沙发 | sofa | 沙发 | 2.0×0.85×0.85 | composite |
| 床 | bed | 床, 床铺 | 2.0×1.6×0.65 | composite |
| 书架 | bookshelf | 书架, 书柜 | 0.8×0.35×1.8 | composite |
| 柜子 | cabinet | 柜子, 橱柜, 衣柜, 电视柜 | 0.8×0.4×1.6 | cuboid |
| 台面 | counter | 厨房台面 | 1.8×0.6×0.9 | cuboid |
| 抽屉柜 | dresser | 五斗柜 | 1.0×0.45×0.85 | cuboid |
| 地毯 | rug | 地毯 | 1.5×2.0×0.04 | cuboid |

### 附属型 (satellite) — 围绕平台排列

| 类型 | 英文名 | 中文别名 | 默认尺寸 (宽×深×高 m) | 几何类型 |
|------|--------|----------|----------------------|----------|
| 椅子 | chair | 椅子, 餐椅 | 0.4×0.4×0.9 | composite |
| 凳子 | stool | 凳子, 吧台凳 | 0.35×0.35×0.7 | composite |
| 扶手椅 | armchair | 扶手椅, 休闲椅 | 0.7×0.7×0.9 | cuboid |
| 长凳 | bench | 长凳, 长椅 | 1.2×0.4×0.5 | composite |
| 脚凳 | ottoman | 脚凳 | 0.5×0.5×0.45 | cuboid |
| 床头柜 | nightstand | 床头柜 | 0.45×0.4×0.55 | composite |
| 灯 | lamp | 灯, 落地灯, 台灯 | 0.2×0.2×1.5 | cylinder |
| 植物 | plant | 植物, 盆栽 | 0.3×0.3×1.0 | cylinder |
| 花瓶 | vase | 花瓶 | 0.15×0.15×0.3 | cylinder |

### 独立型 (standalone) — 独立放置

| 类型 | 英文名 | 中文别名 | 默认尺寸 (宽×深×高 m) | 几何类型 |
|------|--------|----------|----------------------|----------|
| 电视 | tv | 电视, 电视机, 显示器 | 1.2×0.08×0.7 | cuboid |
| 冰箱 | fridge | 冰箱 | 0.8×0.7×1.8 | cuboid |
| 烤箱 | oven | 烤箱, 炉灶 | 0.6×0.6×0.9 | cuboid |
| 洗衣机 | washer | 洗衣机 | 0.6×0.65×0.85 | cylinder |
| 微波炉 | microwave | 微波炉 | 0.5×0.4×0.3 | cuboid |
| 镜子 | mirror | 镜子 | 0.6×0.05×0.9 | cuboid |
| 钟 | clock | 钟, 时钟 | 0.3×0.05×0.3 | cylinder |
| 画 | picture | 画, 照片, 相框 | 0.5×0.04×0.4 | cuboid |
| 垃圾桶 | trash_can | 垃圾桶 | 0.25×0.25×0.4 | cylinder |
| 水槽 | sink | 水槽, 洗手池 | 0.6×0.5×0.25 | cuboid |
| 马桶 | toilet | 马桶 | 0.4×0.65×0.45 | cuboid |
| 浴缸 | bathtub | 浴缸, 浴盆 | 1.5×0.7×0.55 | cuboid |
| 靠垫 | cushion | 靠垫, 抱枕 | 0.45×0.45×0.1 | cuboid |

### 几何基本体

| 类型 | 英文名 | 中文别名 | 默认尺寸 | 几何类型 |
|------|--------|----------|----------|----------|
| 球 | ball | 球, 球体 | D=0.25 | sphere |
| 瓶子 | bottle | 瓶子, 水瓶 | D=0.08 H=0.25 | cylinder |
| 碗 | bowl | 碗, 碟子 | D=0.2 H=0.1 | cylinder |
| 杯子 | cup | 杯子, 水杯, 茶杯 | D=0.08 H=0.12 | cylinder |
| 盒子 | box | 盒子, 箱子 | 0.4×0.3×0.3 | cuboid |
| 书 | book | 书, 书本 | 0.15×0.21×0.03 | cuboid |

---

## 支持的维度描述格式

### 英文

```
# 完整三维
Table: 1.2m wide, 0.8m deep, 0.75m tall

# 直径
a ball 0.3m in diameter

# 部分尺寸（缺失维度使用默认值）
a bench 2m wide
a lamp 1.5m tall
```

### 中文

```
# 完整三维
一张桌子宽1.2米深0.8米高0.75米

# 直径
一个球直径0.3米

# 无尺寸（使用默认值）
一张桌子和四把椅子
```

### 空间指令

系统支持解析以下空间方位指令：

```
# 英文
Place two chairs in front of the table and three behind it.
Put one chair on the left side of the table.

# 中文
两把椅子在桌子前面 三把在桌子后面
一把椅子在桌子左边
```

**注意**: 每面实际能放置的椅子数量受桌面宽度限制。

---

## 示例场景

### 1. 餐厅场景（英文 + 完整尺寸）
```
a table 1.2m wide 0.8m deep 0.75m tall with four chairs 0.4m wide 0.4m deep 0.9m tall
```

### 2. 客厅场景（无尺寸，使用默认值）
```
a sofa with a coffee table and two armchairs
```

### 3. 卧室场景（英文 + 空间指令）
```
a bed 2m wide 1.6m deep 0.6m tall with two nightstands.
Place one nightstand on the left of the bed and one on the right.
```

### 4. 多椅子场景（英文 + 中文混合空间指令）
```
a table 2.4m wide 1.6m deep 0.75m tall with five chairs 0.4m wide 0.4m deep 0.9m tall.
Place two chairs in front of the table and three behind it.
```

### 5. 几何体测试（球体 + 立方体）
```
a ball 3m in diameter and a box 2m wide 1.6m deep 1.2m tall
```

### 6. 纯中文场景
```
一张桌子宽1.2米深0.8米高0.75米 四把椅子 两把在桌子前面 两把在桌子后面
```

### 7. 卫浴场景
```
a toilet and a bathtub and a sink
```

### 8. 办公场景
```
a desk 1.5m wide 0.7m deep 0.75m tall with three chairs
```

---

## 朝向控制 (v2.0 新增)

系统支持解析物体的朝向指令，使附属物体面向或背对平台：

```
# 椅子面对桌子 (前方的椅子会旋转180°朝向桌子)
a table with two chairs in front of the table facing the table

# 椅子背对桌子
a table with chairs facing away from the table

# 中文
一张桌子 两把椅子在桌子前面 正对着桌子
一张桌子 椅子背对着桌子
```

朝向效果：
- 前方(-Y)椅子 `facing toward` → 旋转180°朝+Y（面向桌子）
- 后方(+Y)椅子 `facing toward` → 默认朝向（已面向桌子）
- 左侧(-X)椅子 `facing toward` → 旋转-90°朝+X（面向桌子）
- 右侧(+X)椅子 `facing toward` → 旋转90°朝-X（面向桌子）
- `facing away` 效果相反

## 多平台场景 (v2.0 新增)

系统支持多个不同类型的平台共存：

```
# 桌子 + 沙发 + 椅子（椅子围绕最大的平台-沙发排列）
a table and a sofa with two chairs

# 桌子 + 床
a table and a bed

# 卫浴多物体
a toilet and a bathtub and a sink
```

**限制**: 同一类型的多个平台（如 "两个桌子"）暂不支持，请使用不同类型。

## 卫浴物品 (v2.0 新增)

卫浴物品现在具有复合几何形状：

| 物品 | 部件 |
|------|------|
| 马桶 (toilet) | 水箱 + 座体 |
| 浴缸 (bathtub) | 缸体 + 4条支撑腿 |
| 水槽 (sink) | 台面 + 柜体 |

## 已知限制

1. **每面容量限制**: 每面能放置的椅子数量取决于桌面宽度：
   - 1.2m 宽桌子：最多2把/面（椅子宽0.4m + 间距0.1m）
   - 2.4m 宽桌子：最多4把/面
   - 超出容量的椅子会自动分配到其他面

2. **朝向控制**: 支持 facing toward/away 指令，所有方向（前/后/左/右）的椅子均自动计算正确朝向

3. **中文文本长度**: 中文多字物体名称（>3字）可能无法正确匹配，建议使用简短名称

4. **维度关键词**: 仅支持 `wide/宽`, `deep/深`, `tall/高`, `diameter/直径`；不支持 `long/长`, `thick/厚` 等

5. **单平台**: 当前版本仅支持一个主平台，多个平台并排排列而非独立布局

6. **无纹理**: 所有物体使用纯色材质，无贴图纹理
