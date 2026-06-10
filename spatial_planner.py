"""
确定性空间规划器：从用户请求中提取物体尺寸，计算正确的空间位置。
完全不依赖 LLM，保证坐标计算的正确性。

支持的场景类型（自动识别）：
- 桌椅场景: table + chairs (多面围绕)
- 沙发茶几场景: sofa/table + chairs/seats
- 卧室场景: bed + nightstands
- 通用场景: 任意物体的并排或围绕排列
"""
import re
import math
from object_types import (
    lookup_object, get_category, get_default_dims, get_color,
    get_material, get_display_name, get_geometry, get_builder,
    PLATFORM_TYPES, SATELLITE_TYPES,
)

# _KEYWORD_MAP 在 _fallback_parse 中使用
from object_types import _KEYWORD_MAP


def parse_user_request(user_text):
    """
    从用户请求中解析出物体列表和其尺寸、颜色信息。
    支持三种维度格式：
    1. 完整: "Table: 1.2m wide, 0.8m deep, 0.75m tall"
    2. 直径: "a ball 0.3m in diameter"
    3. 部分: 任何未指定的维度使用注册表默认值
    如果完全没有匹配到尺寸，回退到关键词匹配 + 默认尺寸。
    """
    objects = []
    matched_spans = []  # 跟踪已匹配的文本范围，避免重复

    def _overlaps(start, end):
        for ms, me in matched_spans:
            if start < me and end > ms:
                return True
        return False

    # 模式1: 直径规格 "N.Nm (in) diameter" 或 "直径 N.N米"
    dia_pattern = re.compile(
        r'(?<![0-9.])([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*)*|[一-鿿]+)\s+(\d+\.?\d*)\s*(?:m|米)\s+(?:in\s+)?(?:diameter|直径)',
        re.IGNORECASE
    )
    # 也尝试 "直径N.N米" 模式
    dia_pattern2 = re.compile(
        r'(?:直径|diameter)\s*(\d+\.?\d*)\s*(?:m|米)\s+(?:in\s+)?([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*)*|[一-鿿]+)',
        re.IGNORECASE
    )
    for match in dia_pattern.finditer(user_text):
        if _overlaps(match.start(), match.end()):
            continue
        raw_name = match.group(1).strip()
        dia = float(match.group(2))
        matched_spans.append((match.start(), match.end()))
        _add_object_from_match(objects, raw_name, [dia, dia, dia], user_text)

    for match in dia_pattern2.finditer(user_text):
        if _overlaps(match.start(), match.end()):
            continue
        dia = float(match.group(1))
        raw_name = match.group(2).strip()
        matched_spans.append((match.start(), match.end()))
        _add_object_from_match(objects, raw_name, [dia, dia, dia], user_text)

    # 模式2: 完整三维规格（中英文）
    full_pattern = re.compile(
        r'([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*){0,2}|[一-鿿]+)\s*(?::|,)?\s*'
        r'(\d+\.?\d*)\s*(?:m|米)\s*(?:wide|width|w|宽)\s*(?:,?\s*(?:and\s+)?)?'
        r'(\d+\.?\d*)\s*(?:m|米)\s*(?:deep|depth|d|深)\s*(?:,?\s*(?:and\s+)?)?'
        r'(\d+\.?\d*)\s*(?:m|米)\s*(?:tall|height|h|高)',
        re.IGNORECASE
    )

    for match in full_pattern.finditer(user_text):
        if _overlaps(match.start(), match.end()):
            continue
        raw_name = match.group(1).strip()
        w = float(match.group(2))
        d = float(match.group(3))
        h = float(match.group(4))
        matched_spans.append((match.start(), match.end()))
        _add_object_from_match(objects, raw_name, [w, d, h], user_text)

    # 模式3: 部分尺寸（单独匹配宽、深、高）
    partial_map = {}  # name_lower -> {dim_key: value}
    for dim_key, pattern in [
        ('w', re.compile(r'(?<![0-9.])([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*)*|[一-鿿]+)\s+(\d+\.?\d*)\s*(?:m|米)\s+(?:wide|width|w|宽)\b', re.IGNORECASE)),
        ('d', re.compile(r'(?<![0-9.])([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*)*|[一-鿿]+)\s+(\d+\.?\d*)\s*(?:m|米)\s+(?:deep|depth|d|深)\b', re.IGNORECASE)),
        ('h', re.compile(r'(?<![0-9.])([a-zA-Z]\w*(?:\s+[a-zA-Z]\w*)*|[一-鿿]+)\s+(\d+\.?\d*)\s*(?:m|米)\s+(?:tall|height|h|高)\b', re.IGNORECASE)),
    ]:
        for match in pattern.finditer(user_text):
            if _overlaps(match.start(), match.end()):
                continue
            raw_name = match.group(1).strip().lower()
            val = float(match.group(2))
            if raw_name not in partial_map:
                partial_map[raw_name] = {}
            partial_map[raw_name][dim_key] = val
            matched_spans.append((match.start(), match.end()))

    # 为部分匹配创建对象
    for raw_name, dims_partial in partial_map.items():
        type_key = lookup_object(raw_name)
        default_dims = get_default_dims(type_key) if type_key else [1.0, 1.0, 1.0]
        w = dims_partial.get('w', default_dims[0])
        d = dims_partial.get('d', default_dims[1])
        h = dims_partial.get('h', default_dims[2])
        _add_object_from_match(objects, raw_name, [w, d, h], user_text)

    # 回退: 总是尝试从无尺寸文本中提取额外物体（补齐遗漏的）
    fallback_objects = _fallback_parse(user_text)
    existing_names = {o['name'] for o in objects}
    for fo in fallback_objects:
        if fo['name'] not in existing_names:
            objects.append(fo)
            existing_names.add(fo['name'])

    return objects


def _add_object_from_match(objects, raw_name, dims, user_text):
    """根据匹配的名称和尺寸，创建对象条目并添加到列表。"""
    name_lower = raw_name.lower().strip()
    # 去除前导冠词和连接词
    name_lower = re.sub(r'^(?:a|an|and|with)\s+', '', name_lower)
    # 去除中文数量前缀: 数字+量词 (如 "三把"、"两张"、"一个")
    name_lower = re.sub(
        r'^(?:一|二|两|三|四|五|六|七|八|九|十|'
        r'十一|十二|十三|十四|十五|十六|十七|十八|十九|二十)'
        r'(?:个|张|把|台|条|只|件|盏|本|块|面|间|扇|座)?',
        '', name_lower
    )
    name_lower = name_lower.strip()
    type_key = lookup_object(name_lower)

    if not type_key:
        return

    category = get_category(type_key)
    color = get_color(type_key)
    material = get_material(type_key)
    display_name = get_display_name(type_key)

    if category == 'satellite':
        num_items = _parse_count(user_text, name_lower.rsplit(' ', 1)[-1])
        for c in range(num_items):
            objects.append({
                "name": f"{display_name}_{chr(65 + c)}",
                "type": type_key,
                "dimensions": list(dims),
                "color": list(color),
                "material_name": material,
            })
    else:
        objects.append({
            "name": display_name,
            "type": type_key,
            "dimensions": list(dims),
            "color": list(color),
            "material_name": material,
        })


def _fallback_parse(user_text):
    """无尺寸时的回退解析：扫描整个文本，查找所有已知物体关键词 + 默认尺寸。"""
    objects = []
    seen_types = set()
    text_lower = user_text.lower()

    # 收集所有匹配的关键词及其在文本中的位置
    matches = []
    for keyword, type_key in _KEYWORD_MAP:
        pos = text_lower.find(keyword)
        if pos >= 0:
            # 检查关键词是否在上下文中被前面已匹配的尺寸信息覆盖
            matches.append((pos, len(keyword), keyword, type_key))

    if not matches:
        return objects

    # 按位置排序，优先取更长关键词的匹配，每个类型只取第一个
    matches.sort(key=lambda x: (x[0], -x[1]))  # 按位置升序，同位置按长度降序
    found_types = {}
    used_positions = []  # 跟踪已使用的文本范围
    for pos, length, keyword, type_key in matches:
        # 检查是否与已有匹配重叠（避免 "chair" 和 "armchair" 重复）
        overlaps = False
        for upos, ulen in used_positions:
            if pos < upos + ulen and pos + length > upos:
                overlaps = True
                break
        if overlaps:
            continue
        if type_key not in found_types:
            found_types[type_key] = (pos, keyword)
            used_positions.append((pos, length))

    for type_key, (pos, keyword) in found_types.items():
        category = get_category(type_key)

        # 检测 "another X", "second X", "two Xs", "再一个X" 等同类多实例指示
        multi_indicator = re.search(
            r'(another|second|third|再一|另一|第二|第三|另外)',
            text_lower, re.IGNORECASE
        )

        if category == 'satellite':
            count = _parse_count(text_lower, keyword)
            if count <= 1:
                count = _parse_count(text_lower, type_key)
            if count <= 1:
                count = _parse_count(text_lower, '')
            count = max(count, 1)
            if count > 20:
                count = 20
            if type_key in seen_types:
                continue
            seen_types.add(type_key)
            for c in range(count):
                objects.append({
                    "name": f"{get_display_name(type_key)}_{chr(65 + c)}",
                    "type": type_key,
                    "dimensions": get_default_dims(type_key),
                    "color": get_color(type_key),
                    "material_name": get_material(type_key),
                })
        else:
            # 平台/独立型：检测是否需要创建多个同类型实例
            count = _parse_count(text_lower, keyword)
            if count <= 1:
                count = _parse_count(text_lower, type_key)
            if count <= 1 and multi_indicator:
                # 有 "another" 等指示词 → 至少2个
                # 统计文本中该关键词出现的次数
                occurrences = text_lower.count(keyword)
                count = max(2, occurrences)
            count = max(count, 1)
            if count > 4:
                count = 4  # 限制最多4个同类型平台
            if type_key in seen_types:
                continue
            seen_types.add(type_key)
            display = get_display_name(type_key)
            if count == 1:
                objects.append({
                    "name": display,
                    "type": type_key,
                    "dimensions": get_default_dims(type_key),
                    "color": get_color(type_key),
                    "material_name": get_material(type_key),
                })
            else:
                for c in range(count):
                    objects.append({
                        "name": f"{display}_{chr(65 + c)}",
                        "type": type_key,
                        "dimensions": get_default_dims(type_key),
                        "color": get_color(type_key),
                        "material_name": get_material(type_key),
                    })

    return objects


def _parse_count(text, name_hint):
    """解析物体数量，支持数字(1-20)、英文单词(one-twenty)、中文数字(一-十)"""
    # 中文数字映射
    cn_to_num = {
        '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
    }
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
        'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20,
    }
    # 匹配 "a" 或 "an" + name
    a_match = re.search(r'\b(?:a|an)\s+' + re.escape(name_hint), text, re.IGNORECASE)
    if a_match:
        return 1

    num_match = re.search(r'(\d+)\s*' + re.escape(name_hint), text, re.IGNORECASE)
    if num_match:
        val = int(num_match.group(1))
        return min(val, 20)

    # 中文数字匹配 (如 "五把椅子" → 5, 允许量词在中间)
    if name_hint:
        cn_match = re.search(
            r'(一|二|两|三|四|五|六|七|八|九|十|'
            r'十一|十二|十三|十四|十五|十六|十七|十八|十九|二十)'
            r'(?:个|张|把|台|条|只|件|盏|本|块|面|间|扇|座)?'
            + re.escape(name_hint),
            text
        )
    else:
        cn_match = None
    if cn_match:
        val = cn_to_num.get(cn_match.group(1), 0)
        if val > 0:
            return val

    if name_hint:
        # 尝试单数和复数形式
        hints = [name_hint]
        if name_hint.endswith('s'):
            hints.append(name_hint[:-1])  # chairs -> chair
        else:
            hints.append(name_hint + 's')  # chair -> chairs
        for hint in hints:
            word_match = re.search(
                r'(one|two|three|four|five|six|seven|eight|nine|ten|'
                r'eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|'
                r'eighteen|nineteen|twenty)\s+' + re.escape(hint),
                text, re.IGNORECASE
            )
            if word_match:
                return word_to_num.get(word_match.group(1).lower(), 1)

    return 1


def _apply_rotation_to_satellites(satellites, platform, hints):
    """根据朝向提示和已分配的 side 计算每个卫星的 Z 轴旋转。

    支持逐面朝向（per-side facing），即不同面的卫星可以有不同的朝向：
    - 全局 facing（hints['facing']）作为默认值
    - 逐面 facing（hints['front_facing'], hints['back_facing'] 等）覆盖全局值
    """
    if not hints:
        return
    facing = hints.get('facing', 'default')

    # 检查是否有任何朝向指令（全局或逐面）
    has_any_facing = facing != 'default' or any(
        hints.get(f'{s}_facing') for s in ['front', 'back', 'left', 'right']
    )
    if not has_any_facing:
        return

    for sat in satellites:
        side = sat.get('side', None)
        # 回退：如果 side 字段不存在，使用几何判断（平台的相对方位）
        if side not in ('front', 'back', 'left', 'right'):
            sx, sy = sat['location'][0], sat['location'][1]
            px, py = platform['location'][0], platform['location'][1]
            dx, dy = sx - px, sy - py
            if abs(dy) > abs(dx):
                side = 'front' if dy < 0 else 'back'
            else:
                side = 'left' if dx < 0 else 'right'

        # 逐面朝向覆盖全局朝向
        effective_facing = hints.get(f'{side}_facing', facing)

        rot_z = 0.0
        if effective_facing == 'toward':
            if side == 'front':
                rot_z = 3.14159   # 前方 → 朝+Y（面向平台）
            elif side == 'back':
                rot_z = 0.0        # 后方 → 朝-Y（默认面向平台）
            elif side == 'left':
                rot_z = 1.5708     # 左侧 → 朝+X（面向平台）
            elif side == 'right':
                rot_z = -1.5708    # 右侧 → 朝-X（面向平台）
        elif effective_facing == 'away':
            if side == 'front':
                rot_z = 0.0        # 前方 → 朝-Y（背离平台）
            elif side == 'back':
                rot_z = 3.14159    # 后方 → 朝+Y（背离平台）
            elif side == 'left':
                rot_z = -1.5708    # 左侧 → 朝-X（背离平台）
            elif side == 'right':
                rot_z = 1.5708     # 右侧 → 朝+X（背离平台）
        sat['rotation_z'] = rot_z


def _check_platform_satellite_overlap(platform, satellites):
    """检查平台与卫星是否重叠，返回 True 表示有重叠。"""
    pd = platform['dimensions']
    pl = platform['location']
    for sat in satellites:
        sd = sat['dimensions']
        sl = sat['location']
        if abs(pl[0] - sl[0]) < pd[0]/2 + sd[0]/2 + 0.05 and abs(pl[1] - sl[1]) < pd[1]/2 + sd[1]/2 + 0.05:
            return True
    return False


def _parse_platform_relations(user_text, platforms):
    """解析平台间相对位置 (如 'A to the left of B' / 'A在B的左边')。"""
    relations = {}
    if len(platforms) < 2 or not user_text:
        return relations
    name_to_obj = {p['name'].lower(): p['name'] for p in platforms}
    side_map = [
        ('left', ['to the left of', 'on the left of', '左边', '左侧']),
        ('right', ['to the right of', 'on the right of', '右边', '右侧']),
        ('front', ['in front of', '前面', '前方']),
        ('back', ['behind', '后面', '后方']),
    ]
    for side, patterns in side_map:
        for pat in patterns:
            m = re.search(r'(\w+)\s*' + pat + r'\s*(\w+)', user_text, re.IGNORECASE)
            if m:
                a_lower = m.group(1).lower()
                b_lower = m.group(2).lower()
                for pname_lower, pname in name_to_obj.items():
                    if pname_lower in a_lower or a_lower in pname_lower:
                        for pname2_lower, pname2 in name_to_obj.items():
                            if pname2 != pname and (pname2_lower in b_lower or b_lower in pname2_lower):
                                relations[pname] = {'relation': side, 'target': pname2}
    return relations


def compute_positions(objects, user_text=''):
    """
    根据物体类型和尺寸计算正确的空间位置。
    支持多平台相对定位、卫星归属、穿模检测。
    """
    if not objects:
        return objects

    # 分类
    platforms = [o for o in objects if o['type'] in PLATFORM_TYPES]
    satellites = [o for o in objects if o['type'] in SATELLITE_TYPES]
    others = [o for o in objects if o['type'] not in PLATFORM_TYPES and o['type'] not in SATELLITE_TYPES]

    # 如果没有平台，所有物体沿 X 轴排列
    if not platforms:
        x = 0.0
        for obj in objects:
            dims = obj['dimensions']
            obj['location'] = [x, 0, dims[2] / 2]
            x += dims[0] + 0.3
        return objects

    # 按尺寸对平台排序：最大的先放置（在原点）
    platforms.sort(key=lambda p: -(p['dimensions'][0] * p['dimensions'][1]))

    # 放置平台
    placed_platforms = []
    current_x = 0.0
    for i, plat in enumerate(platforms):
        dims = plat['dimensions']
        if i == 0:
            plat['location'] = [0, 0, dims[2] / 2]
        else:
            prev = placed_platforms[-1]
            p_dims = prev['dimensions']
            current_x += p_dims[0] / 2 + dims[0] / 2 + 0.5
            plat['location'] = [current_x, 0, dims[2] / 2]
        placed_platforms.append(plat)

    # 将附属物体分配到主平台（最大的）
    main_platform = platforms[0]

    if satellites:
        # 解析用户的空间指令（如果有）
        sat_type = satellites[0]['type']
        hints = _parse_placement_hints(user_text, sat_type) if user_text else None
        _place_satellites_4side(satellites, main_platform, hints)
        _apply_rotation_to_satellites(satellites, main_platform, hints)

    # 放置其余平台（多平台场景）
    for i, plat in enumerate(platforms):
        if i == 0:
            continue
        dims = plat['dimensions']
        prev = platforms[i - 1]
        plat['location'] = [prev['location'][0] + prev['dimensions'][0]/2 + dims[0]/2 + 0.5,
                            0, dims[2]/2]
        if satellites and _check_platform_satellite_overlap(plat, satellites):
            plat['location'][0] += 1.0

    # 其他物体沿 Y 轴远离方向排列
    if others:
        y_offset = main_platform['location'][1] + main_platform['dimensions'][1] + 0.5
        for i, obj in enumerate(others):
            dims = obj['dimensions']
            obj['location'] = [0, y_offset + i * 1.0, dims[2] / 2]

    return objects


def _parse_placement_hints(user_text, satellite_type):
    """从用户文本中提取空间方位指令。

    匹配模式:
      - "N chairs in front of (the table)" → front=N
      - "N chairs behind (the table)" → back=N
      - "N chairs on the left (side) of (the table)" → left=N
      - "N chairs on the right (side) of (the table)" → right=N
      - "the rest behind / on the side" → remaining=N

    支持中英文:
      - front/前面/前方, back/后面/后方, left/左边/左侧, right/右边/右侧
      - the rest/剩下的/其余的/剩余

    返回 dict 或 None。
    """
    hints = {}
    text = user_text.lower()

    # 数字词映射（中英文）
    num_words = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    }

    # 方位词映射 → (side_key, sign)
    position_map = [
        ('front', ['in front of', 'in the front', 'in front', 'before', 'front', '前面', '前方', '前', '桌前', '前边']),
        ('back', ['in the back', 'behind', 'after', 'back', '后面', '后方', '后', '桌后', '后边']),
        ('left', ['on the left', 'left side', 'to the left', '左边', '左侧', '左', '左边']),
        ('right', ['on the right', 'right side', 'to the right', '右边', '右侧', '右', '右边']),
    ]

    # 跟踪已匹配的文本范围，防止子串关键词重复计数
    matched_spans = []

    def _overlaps(start, end):
        for ms, me in matched_spans:
            if start < me and end > ms:
                return True
        return False

    # 匹配 "N chairs/椅子  in front / 前面"
    num_pattern = r'(' + '|'.join(re.escape(w) for w in num_words.keys()) + r'|\d+)'
    type_pattern = r'(' + re.escape(satellite_type) + r's?|' + re.escape(satellite_type) + r')'

    for side_key, keywords in position_map:
        for kw in keywords:
            # 英文: "two chairs in front of the table"
            pattern = num_pattern + r'\s*' + type_pattern + r'?\s*' + re.escape(kw)
            for m in re.finditer(pattern, text, re.IGNORECASE):
                if _overlaps(m.start(), m.end()):
                    continue
                n_str = m.group(1)
                n = num_words.get(n_str.lower())
                if n is None:
                    n = int(n_str)
                hints[side_key] = hints.get(side_key, 0) + n
                # 记录该方位匹配到的物体类型（用于混合类型场景下的正确分配）
                if m.lastindex and m.lastindex >= 2:
                    _type_name = m.group(2)
                    if _type_name:
                        _type_clean = _type_name.lower().rstrip('s')
                        hints.setdefault('_types', {})
                        if side_key not in hints['_types']:
                            hints['_types'][side_key] = _type_clean
                matched_spans.append((m.start(), m.end()))

            # 模式: "a/an <type> <position>" (无显式数字，隐含 count=1)
            article_pattern = (r'(?:a|an)\s+' + type_pattern +
                               r'\s*' + re.escape(kw))
            for am in re.finditer(article_pattern, text, re.IGNORECASE):
                if _overlaps(am.start(), am.end()):
                    continue
                hints[side_key] = hints.get(side_key, 0) + 1
                # 记录该方位对应的物体类型
                if am.group(1):
                    _type_name = am.group(1).lower().rstrip('s')
                    hints.setdefault('_types', {})
                    if side_key not in hints['_types']:
                        hints['_types'][side_key] = _type_name
                matched_spans.append((am.start(), am.end()))

    # ======== 通用回退匹配：数量 + 任意词 + 方位词（处理混合附属类型，如 nightstands + lamp） ========
    for side_key, keywords in position_map:
        for kw in keywords:
            # 模式: "two nightstands on the left" / "one lamp on the right"（任意物体类型）
            pattern_any = num_pattern + r'\s+(\w+)\s+' + re.escape(kw)
            for m in re.finditer(pattern_any, text, re.IGNORECASE):
                if _overlaps(m.start(), m.end()):
                    continue
                n_str = m.group(1)
                n = num_words.get(n_str.lower())
                if n is None:
                    try:
                        n = int(n_str)
                    except ValueError:
                        continue
                hints[side_key] = hints.get(side_key, 0) + n
                # 记录该方位对应的物体类型
                if m.lastindex and m.lastindex >= 2 and m.group(2):
                    _type_name = m.group(2).lower().rstrip('s')
                    hints.setdefault('_types', {})
                    if side_key not in hints['_types']:
                        hints['_types'][side_key] = _type_name
                matched_spans.append((m.start(), m.end()))

            # 模式: "a lamp on the right"（隐含数量1，任意物体类型）
            article_any = r'(?:a|an)\s+(\w+)\s+' + re.escape(kw)
            for am in re.finditer(article_any, text, re.IGNORECASE):
                if _overlaps(am.start(), am.end()):
                    continue
                hints[side_key] = hints.get(side_key, 0) + 1
                # 记录该方位对应的物体类型
                if am.group(1):
                    _type_name = am.group(1).lower().rstrip('s')
                    hints.setdefault('_types', {})
                    if side_key not in hints['_types']:
                        hints['_types'][side_key] = _type_name
                matched_spans.append((am.start(), am.end()))

    # 匹配 "the rest / remaining / 剩下的 / 其余  behind/on the side"
    for side_key, keywords in position_map:
        for kw in keywords:
            rest_pattern = r'(?:the\s+rest|remaining|others?|剩下的|其余的|剩余)' + r'.*?' + re.escape(kw)
            m = re.search(rest_pattern, text, re.IGNORECASE)
            if m:
                hints[f'{side_key}_rest'] = True

    # 匹配中文 "N把椅子在桌子前面/后面/左边/右边"
    cn_digits = '一二两三四五六七八九十'
    cn_side_map = [
        ('front', ['前面', '前方', '前边', '正面']),
        ('back', ['后面', '后方', '后边', '背面']),
        ('left', ['左边', '左侧', '左面']),
        ('right', ['右边', '右侧', '右面']),
    ]
    # 手动扫描：找到每个 (数字, 方位词) 对
    for side_key, keywords in cn_side_map:
        for kw in keywords:
            kw_pos = text.find(kw)
            if kw_pos < 0:
                continue
            # 向前搜索最近的数字
            before = text[:kw_pos]
            # 找最后一个中文数字或阿拉伯数字
            cn_match = None
            cn_pos = -1
            for ch_idx, ch in enumerate(before):
                if ch in cn_digits:
                    cn_pos = ch_idx
                    cn_match = ch
            # 也找阿拉伯数字
            digit_match = re.search(r'(\d+)', before)
            digit_pos = digit_match.start() if digit_match else -1

            if cn_pos >= 0 and cn_pos > digit_pos:
                n = num_words.get(cn_match, 0)
            elif digit_pos >= 0:
                n = int(digit_match.group(1))
            else:
                continue
            if n > 0:
                hints[side_key] = hints.get(side_key, 0) + n

    # ======== 朝向检测（容错拼写处理） ========
    # 用户可能输入 "faing" (typo) 而不是 "facing"
    _FACING_FUZZY = r'f(?:acing|aing|faing|facng|facin|faceing|fasing|facingg|fceing|fcaing)'

    # 检测全局朝向指令: "facing the table" / "正对着桌子" / "背对桌子"
    facing_toward = re.search(
        rf'(?:{_FACING_FUZZY}\s+(?:toward|the|to)|正对着|面向|朝着|朝向)',
        text, re.IGNORECASE
    )
    facing_away = re.search(
        rf'(?:{_FACING_FUZZY}\s+away|背对|背对着|背朝)',
        text, re.IGNORECASE
    )
    if facing_toward:
        hints['facing'] = 'toward'
    elif facing_away:
        hints['facing'] = 'away'

    # ======== 逐面朝向检测 ========
    # 支持同一个场景中不同面的椅子有不同的朝向
    # 如: "two in front facing the table and two behind facing away"
    # 使用防跨越标记，确保不会跨过其他朝向关键词（含中文方位词）
    _NOT_ACROSS_SIDE = (
        r'(?:(?!\b(?:front|back|left|right|behind|ahead)\b'
        r'|前面|后面|左边|右边|前方|后方|左侧|右侧).)'
    )
    per_side_facing = {
        'front': [
            # 英文: in front of / in front / in the front / front ... facing ...
            (rf'(?:in front of|in the front|in front|front){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+(?:toward|the|to)', 'toward'),
            (rf'(?:in front of|in the front|in front|front){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+away', 'away'),
            # 中文: 前面/前方 ... 正对/背对/朝向/面向 ...
            (r'(?:前面|前方|前边|正面)[^。]{0,40}?(?:正对着|面向|朝着|朝向)', 'toward'),
            (r'(?:前面|前方|前边|正面)[^。]{0,40}?(?:背对|背对着|背朝|背着)', 'away'),
        ],
        'back': [
            (rf'(?:behind|in the back|back){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+(?:toward|the|to)', 'toward'),
            (rf'(?:behind|in the back|back){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+away', 'away'),
            (r'(?:后面|后方|后边|背面)[^。]{0,40}?(?:正对着|面向|朝着|朝向)', 'toward'),
            (r'(?:后面|后方|后边|背面)[^。]{0,40}?(?:背对|背对着|背朝|背着)', 'away'),
        ],
        'left': [
            (rf'(?:on the left|to the left|left side|left){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+(?:toward|the|to)', 'toward'),
            (rf'(?:on the left|to the left|left side|left){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+away', 'away'),
            (r'(?:左边|左侧|左面)[^。]{0,40}?(?:正对着|面向|朝着|朝向)', 'toward'),
            (r'(?:左边|左侧|左面)[^。]{0,40}?(?:背对|背对着|背朝|背着)', 'away'),
        ],
        'right': [
            (rf'(?:on the right|to the right|right side|right){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+(?:toward|the|to)', 'toward'),
            (rf'(?:on the right|to the right|right side|right){_NOT_ACROSS_SIDE}*?{_FACING_FUZZY}\s+away', 'away'),
            (r'(?:右边|右侧|右面)[^。]{0,40}?(?:正对着|面向|朝着|朝向)', 'toward'),
            (r'(?:右边|右侧|右面)[^。]{0,40}?(?:背对|背对着|背朝|背着)', 'away'),
        ],
    }
    for side, patterns in per_side_facing.items():
        for pattern, value in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                hints[f'{side}_facing'] = value

    return hints if hints else None


def _reorder_satellites_by_side_types(satellites, hints, side_counts):
    """根据 hints 中记录的方位→类型映射，重排卫星列表，
    使得指定类型的卫星出现在对应方位分配的靠前位置。
    side_counts: 各方位分配数量，如 {'front':0, 'back':0, 'left':1, 'right':2}"""
    type_map = hints.get('_types', {}) if hints else {}
    if not type_map:
        return

    # 按方位处理顺序匹配
    side_order = ['front', 'back', 'left', 'right']
    reordered = []
    used = set()

    for side in side_order:
        expected_type = type_map.get(side)
        count_needed = side_counts.get(side, 0)
        if not expected_type or count_needed == 0:
            continue

        found = 0
        for i, sat in enumerate(satellites):
            if i in used:
                continue
            if found >= count_needed:
                break
            sat_type = sat.get('type', '').lower().rstrip('s')
            if sat_type == expected_type:
                reordered.append(sat)
                used.add(i)
                found += 1

    # 剩余卫星放到末尾
    for i, sat in enumerate(satellites):
        if i not in used:
            reordered.append(sat)

    satellites[:] = reordered


def _place_satellites_4side(satellites, platform, hints=None):
    """
    将附属物体分布到平台的4面（front, back, left, right）。
    如果有 hints，优先按 hints 分配；否则自适应容量贪心分配。
    """
    p_dims = platform['dimensions']
    p_loc = platform['location']
    gap = 0.25
    margin = 0.1
    num = len(satellites)

    if not satellites:
        return

    sat_dims = satellites[0]['dimensions']
    chair_w = sat_dims[0]
    chair_d = sat_dims[1]

    def _capacity(edge_len, sat_span):
        return max(1, int((edge_len - 2 * margin + 0.1) / (sat_span + 0.1)))

    front_cap = _capacity(p_dims[0], chair_w)
    back_cap = _capacity(p_dims[0], chair_w)
    left_cap = _capacity(p_dims[1], chair_d)
    right_cap = _capacity(p_dims[1], chair_d)

    # 确定分配方案
    front_n = back_n = left_n = right_n = 0
    if hints:
        # 使用用户指定的分布
        hinted_front = hints.get('front', 0)
        hinted_back = hints.get('back', 0)
        hinted_left = hints.get('left', 0)
        hinted_right = hints.get('right', 0)
        hinted_total = hinted_front + hinted_back + hinted_left + hinted_right

        has_rest_hint = any(k.endswith('_rest') for k in hints)

        if hinted_total > 0:
            # 限制在容量内
            front_n = min(hinted_front, front_cap)
            back_n = min(hinted_back, back_cap)
            left_n = min(hinted_left, left_cap)
            right_n = min(hinted_right, right_cap)

            # 如果有 "the rest behind" 之类的提示，剩余的全部放到对应面
            if has_rest_hint:
                placed = front_n + back_n + left_n + right_n
                remaining = num - placed
                for side_key in ['back', 'front', 'left', 'right']:
                    if hints.get(f'{side_key}_rest') and remaining > 0:
                        cap = {'front': front_cap, 'back': back_cap, 'left': left_cap, 'right': right_cap}[side_key]
                        extra = min(remaining, cap)
                        if side_key == 'front':
                            front_n += extra
                        elif side_key == 'back':
                            back_n += extra
                        elif side_key == 'left':
                            left_n += extra
                        elif side_key == 'right':
                            right_n += extra
                        remaining -= extra
            else:
                # 没有 rest 提示：剩余椅子按容量分配
                placed = front_n + back_n + left_n + right_n
                remaining = num - placed
                for side_n, cap, key in [
                    (back_n, back_cap, 'back'),
                    (front_n, front_cap, 'front'),
                    (left_n, left_cap, 'left'),
                    (right_n, right_cap, 'right'),
                ]:
                    if remaining <= 0:
                        break
                    extra = min(remaining, cap - {'front': front_n, 'back': back_n, 'left': left_n, 'right': right_n}[key])
                    if extra > 0:
                        if key == 'front':
                            front_n += extra
                        elif key == 'back':
                            back_n += extra
                        elif key == 'left':
                            left_n += extra
                        elif key == 'right':
                            right_n += extra
                        remaining -= extra
        else:
            # hints 中没有数字，使用默认贪心
            pass

        # 如果没有有效分配，回退到贪心
        if (front_n + back_n + left_n + right_n) > 0:
            # 格式: (side_name, sign, along_axis, edge_len, sat_span, count)
            side_order = [
                ('front', -1, 'Y', p_dims[0], chair_w, front_n),
                ('back', 1, 'Y', p_dims[0], chair_w, back_n),
                ('left', -1, 'X', p_dims[1], chair_d, left_n),
                ('right', 1, 'X', p_dims[1], chair_d, right_n),
            ]
        else:
            hints = None  # 回退

    if not hints or front_n + back_n + left_n + right_n == 0:
        # 默认贪心分配: front → back → left → right
        side_order = [
            ('front', front_cap, -1, 'Y', p_dims[0], chair_w),
            ('back', back_cap, 1, 'Y', p_dims[0], chair_w),
            ('left', left_cap, -1, 'X', p_dims[1], chair_d),
            ('right', right_cap, 1, 'X', p_dims[1], chair_d),
        ]

        assignment = []
        remaining = num
        for side_name, cap, sign, along_axis, edge_len, sat_span in side_order:
            take = min(cap, remaining)
            if take > 0:
                assignment.append((side_name, sign, along_axis, edge_len, sat_span, take))
                remaining -= take
            if remaining <= 0:
                break
        side_order = assignment

    # 根据 hints 中记录的方位→类型映射重排卫星列表
    if hints and hints.get('_types'):
        _reorder_satellites_by_side_types(
            satellites, hints,
            {'front': front_n, 'back': back_n, 'left': left_n, 'right': right_n}
        )

    # 放置
    sat_idx = 0
    for side_name, sign, along_axis, edge_len, sat_span, count in side_order:
        if count == 0:
            continue
        if count == 1:
            offsets = [0.0]
        else:
            available = edge_len - 2 * margin
            step = available / (count - 1)
            offsets = [-available / 2 + j * step for j in range(count)]

        for j in range(count):
            if sat_idx >= num:
                break
            sat = satellites[sat_idx]
            sd = sat['dimensions']

            if along_axis == 'Y':
                y = p_loc[1] + sign * (p_dims[1] / 2 + sd[1] / 2 + gap)
                x = p_loc[0] + offsets[j]
                sat['location'] = [x, y, sd[2] / 2]
            else:
                x = p_loc[0] + sign * (p_dims[0] / 2 + sd[0] / 2 + gap)
                y = p_loc[1] + offsets[j]
                sat['location'] = [x, y, sd[2] / 2]

            sat['side'] = side_name
            sat_idx += 1

    # 卫星间重叠检测和微调
    _resolve_satellite_overlaps(satellites)


def _resolve_satellite_overlaps(satellites, min_gap=0.05):
    """检测卫星之间的 AABB 重叠并微调位置。"""
    for _ in range(3):  # 最多3轮微调
        moved = False
        for i in range(len(satellites)):
            for j in range(i + 1, len(satellites)):
                a = satellites[i]
                b = satellites[j]
                ad = a['dimensions']
                bd = b['dimensions']
                la = a['location']
                lb = b['location']

                dx = abs(la[0] - lb[0])
                dy = abs(la[1] - lb[1])
                min_dx = ad[0] / 2 + bd[0] / 2 + min_gap
                min_dy = ad[1] / 2 + bd[1] / 2 + min_gap

                if dx < min_dx and dy < min_dy:
                    # 选择重叠较小的轴进行微调
                    overlap_x = min_dx - dx
                    overlap_y = min_dy - dy
                    if overlap_x < overlap_y:
                        nudge = overlap_x / 2 + 0.01
                        if la[0] > lb[0]:
                            la[0] += nudge
                            lb[0] -= nudge
                        else:
                            la[0] -= nudge
                            lb[0] += nudge
                    else:
                        nudge = overlap_y / 2 + 0.01
                        if la[1] > lb[1]:
                            la[1] += nudge
                            lb[1] -= nudge
                        else:
                            la[1] -= nudge
                            lb[1] += nudge
                    moved = True
        if not moved:
            break


def generate_spec_from_request(user_text):
    """
    从用户请求直接生成完整规格（不依赖 LLM）。
    返回: {"objects": [...]}
    """
    objects = parse_user_request(user_text)
    objects = compute_positions(objects, user_text)

    spec_objects = []
    for obj in objects:
        spec_objects.append({
            "name": obj["name"],
            "type": obj.get("type", "object"),
            "dimensions": obj["dimensions"],
            "location": obj.get("location", [0, 0, obj["dimensions"][2] / 2]),
            "color": obj["color"],
            "material_name": obj["material_name"],
            "rotation_z": obj.get("rotation_z", 0.0),
        })

    return {"objects": spec_objects}
