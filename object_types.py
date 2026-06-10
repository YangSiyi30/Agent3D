"""
集中式物体类型注册表 — 所有物体类型的唯一数据源。

所有模块（spatial_planner, code_generator, deterministic_fixer, blender_env）
从此文件导入类型信息，避免多处重复定义和不一致。

支持约 30 种常见物体，分为三类：
- platform:  可被其他物体围绕的大型物体（桌子、沙发、床...）
- satellite: 围绕平台的附属物体（椅子、凳子、床头柜...）
- standalone: 独立物体（电视、冰箱、球、瓶子...）

支持四种几何类型：
- composite: 多部件组合（桌子=桌面+腿，椅子=座面+靠背+腿...）
- cuboid:    简单立方体
- cylinder:  圆柱体
- sphere:    球体
"""

# ============================================================
# 主注册表
# ============================================================
OBJECT_REGISTRY = {
    # === 家具 - 平台型 ===
    'table': {
        'display_name': 'Table',
        'default_dims': [1.2, 0.8, 0.75],
        'color': [0.4, 0.25, 0.1],
        'material': 'Wood',
        'category': 'platform',
        'geometry': 'composite',
        'builder': 'table',
        'aliases': ['desk', 'dining table', 'coffee table', 'work table'],
        'zh_aliases': ['桌子', '餐桌', '书桌', '茶几', '饭桌', '办公桌'],
    },
    'sofa': {
        'display_name': 'Sofa',
        'default_dims': [2.0, 0.85, 0.85],
        'color': [0.3, 0.2, 0.4],
        'material': 'Fabric',
        'category': 'platform',
        'geometry': 'composite',
        'builder': 'sofa',
        'aliases': ['couch', 'loveseat', 'settee'],
        'zh_aliases': ['沙发'],
    },
    'bed': {
        'display_name': 'Bed',
        'default_dims': [2.0, 1.6, 0.65],
        'color': [0.9, 0.9, 0.95],
        'material': 'Fabric',
        'category': 'platform',
        'geometry': 'composite',
        'builder': 'bed',
        'aliases': ['double bed', 'queen bed', 'single bed'],
        'zh_aliases': ['床', '床铺', '双人床', '单人床'],
    },
    'bookshelf': {
        'display_name': 'Bookshelf',
        'default_dims': [0.8, 0.35, 1.8],
        'color': [0.35, 0.2, 0.1],
        'material': 'Wood',
        'category': 'platform',
        'geometry': 'composite',
        'builder': 'bookshelf',
        'aliases': ['shelf', 'bookcase', 'book shelf', 'book case'],
        'zh_aliases': ['书架', '书柜', '书橱'],
    },
    'cabinet': {
        'display_name': 'Cabinet',
        'default_dims': [0.8, 0.4, 1.6],
        'color': [0.35, 0.2, 0.1],
        'material': 'Wood',
        'category': 'platform',
        'geometry': 'cuboid',
        'aliases': ['cupboard', 'wardrobe', 'closet', 'storage cabinet', 'tv stand'],
        'zh_aliases': ['柜子', '橱柜', '衣柜', '电视柜'],
    },
    'counter': {
        'display_name': 'Counter',
        'default_dims': [1.8, 0.6, 0.9],
        'color': [0.5, 0.5, 0.5],
        'material': 'Stone',
        'category': 'platform',
        'geometry': 'cuboid',
        'aliases': ['kitchen counter', 'island', 'bar counter'],
    },
    'dresser': {
        'display_name': 'Dresser',
        'default_dims': [1.0, 0.45, 0.85],
        'color': [0.35, 0.2, 0.1],
        'material': 'Wood',
        'category': 'platform',
        'geometry': 'cuboid',
        'aliases': ['chest of drawers', 'bureau', 'drawer chest', 'commode'],
    },
    'rug': {
        'display_name': 'Rug',
        'default_dims': [1.5, 2.0, 0.04],
        'color': [0.7, 0.2, 0.2],
        'material': 'Fabric',
        'category': 'platform',
        'geometry': 'cuboid',
        'aliases': ['carpet', 'mat', 'floor mat'],
    },

    # === 家具 - 附属型 ===
    'chair': {
        'display_name': 'Chair',
        'default_dims': [0.4, 0.4, 0.9],
        'color': [0.2, 0.2, 0.2],
        'material': 'Metal',
        'category': 'satellite',
        'geometry': 'composite',
        'builder': 'chair',
        'aliases': ['seat', 'dining chair', 'wooden chair', 'metal chair'],
        'zh_aliases': ['椅子', '餐椅', '木椅', '靠背椅'],
    },
    'stool': {
        'display_name': 'Stool',
        'default_dims': [0.35, 0.35, 0.7],
        'color': [0.25, 0.15, 0.05],
        'material': 'Wood',
        'category': 'satellite',
        'geometry': 'composite',
        'builder': 'chair',
        'aliases': ['bar stool', 'barstool'],
        'zh_aliases': ['凳子', '吧台凳', '圆凳'],
    },
    'armchair': {
        'display_name': 'Armchair',
        'default_dims': [0.7, 0.7, 0.9],
        'color': [0.3, 0.2, 0.4],
        'material': 'Fabric',
        'category': 'satellite',
        'geometry': 'cuboid',
        'aliases': ['arm chair', 'easy chair', 'lounge chair'],
        'zh_aliases': ['扶手椅', '休闲椅'],
    },
    'bench': {
        'display_name': 'Bench',
        'default_dims': [1.2, 0.4, 0.5],
        'color': [0.35, 0.2, 0.1],
        'material': 'Wood',
        'category': 'satellite',
        'geometry': 'composite',
        'builder': 'table',
        'aliases': ['wooden bench', 'park bench', 'seating bench'],
        'zh_aliases': ['长凳', '长椅', '条凳'],
    },
    'ottoman': {
        'display_name': 'Ottoman',
        'default_dims': [0.5, 0.5, 0.45],
        'color': [0.3, 0.2, 0.3],
        'material': 'Fabric',
        'category': 'satellite',
        'geometry': 'cuboid',
        'aliases': ['footstool', 'pouf', 'hassock'],
    },
    'nightstand': {
        'display_name': 'Nightstand',
        'default_dims': [0.45, 0.4, 0.55],
        'color': [0.35, 0.2, 0.1],
        'material': 'Wood',
        'category': 'satellite',
        'geometry': 'composite',
        'builder': 'table',
        'aliases': ['bedside table', 'night stand', 'bed stand'],
    },
    'lamp': {
        'display_name': 'Lamp',
        'default_dims': [0.2, 0.2, 1.5],
        'color': [0.8, 0.8, 0.3],
        'material': 'Metal',
        'category': 'satellite',
        'geometry': 'cylinder',
        'aliases': ['floor lamp', 'standing lamp', 'light'],
        'zh_aliases': ['灯', '台灯', '落地灯', '吊灯'],
    },
    'plant': {
        'display_name': 'Plant',
        'default_dims': [0.3, 0.3, 1.0],
        'color': [0.1, 0.6, 0.2],
        'material': 'Organic',
        'category': 'satellite',
        'geometry': 'cylinder',
        'aliases': ['potted plant', 'houseplant', 'tree', 'indoor plant'],
        'zh_aliases': ['植物', '盆栽', '绿植', '花盆'],
    },
    'vase': {
        'display_name': 'Vase',
        'default_dims': [0.15, 0.15, 0.3],
        'color': [0.6, 0.5, 0.7],
        'material': 'Ceramic',
        'category': 'satellite',
        'geometry': 'cylinder',
        'aliases': ['flower vase', 'decorative vase', 'pot'],
        'zh_aliases': ['花瓶', '装饰瓶'],
    },

    # === 家电/电子设备 ===
    'tv': {
        'display_name': 'TV',
        'default_dims': [1.2, 0.08, 0.7],
        'color': [0.05, 0.05, 0.05],
        'material': 'Plastic',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['television', 'monitor', 'screen', 'flat screen', 'tv set'],
        'zh_aliases': ['电视', '电视机', '显示器', '屏幕'],
    },
    'fridge': {
        'display_name': 'Fridge',
        'default_dims': [0.8, 0.7, 1.8],
        'color': [0.8, 0.8, 0.8],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['refrigerator', 'fridge freezer', 'ice box'],
        'zh_aliases': ['冰箱', '冰柜'],
    },
    'oven': {
        'display_name': 'Oven',
        'default_dims': [0.6, 0.6, 0.9],
        'color': [0.3, 0.3, 0.3],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['stove', 'cooker', 'range'],
        'zh_aliases': ['烤箱', '炉灶', '灶台'],
    },
    'washer': {
        'display_name': 'Washer',
        'default_dims': [0.6, 0.65, 0.85],
        'color': [0.9, 0.9, 0.9],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['washing machine', 'laundry machine', 'dryer'],
    },
    'microwave': {
        'display_name': 'Microwave',
        'default_dims': [0.5, 0.4, 0.3],
        'color': [0.7, 0.7, 0.7],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['microwave oven'],
    },

    # === 装饰/卫浴/其他 ===
    'mirror': {
        'display_name': 'Mirror',
        'default_dims': [0.6, 0.05, 0.9],
        'color': [0.8, 0.85, 0.9],
        'material': 'Glass',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['wall mirror', 'looking glass'],
        'zh_aliases': ['镜子', '穿衣镜'],
    },
    'clock': {
        'display_name': 'Clock',
        'default_dims': [0.3, 0.05, 0.3],
        'color': [0.9, 0.9, 0.9],
        'material': 'Plastic',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['wall clock', 'analog clock'],
        'zh_aliases': ['钟', '时钟', '挂钟'],
    },
    'picture': {
        'display_name': 'Picture',
        'default_dims': [0.5, 0.04, 0.4],
        'color': [0.6, 0.4, 0.2],
        'material': 'Wood',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['painting', 'picture frame', 'photo frame', 'artwork'],
        'zh_aliases': ['画', '照片', '相框', '装饰画'],
    },
    'trash_can': {
        'display_name': 'TrashCan',
        'default_dims': [0.25, 0.25, 0.4],
        'color': [0.3, 0.3, 0.3],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['bin', 'garbage can', 'waste basket', 'trash bin'],
        'zh_aliases': ['垃圾桶', '垃圾箱', '废纸篓'],
    },
    'sink': {
        'display_name': 'Sink',
        'default_dims': [0.6, 0.5, 0.85],
        'color': [0.8, 0.8, 0.8],
        'material': 'Metal',
        'category': 'standalone',
        'geometry': 'composite',
        'builder': 'sink',
        'aliases': ['kitchen sink', 'bathroom sink', 'basin', 'washbasin'],
        'zh_aliases': ['水槽', '洗手池', '洗脸盆'],
    },
    'toilet': {
        'display_name': 'Toilet',
        'default_dims': [0.4, 0.65, 0.45],
        'color': [0.95, 0.95, 0.95],
        'material': 'Ceramic',
        'category': 'standalone',
        'geometry': 'composite',
        'builder': 'toilet',
        'aliases': ['water closet', 'wc', 'lavatory'],
        'zh_aliases': ['马桶', '坐便器'],
    },
    'bathtub': {
        'display_name': 'Bathtub',
        'default_dims': [1.5, 0.7, 0.55],
        'color': [0.9, 0.9, 0.9],
        'material': 'Ceramic',
        'category': 'standalone',
        'geometry': 'composite',
        'builder': 'bathtub',
        'aliases': ['bath', 'tub', 'bath tub'],
        'zh_aliases': ['浴缸', '浴盆', '澡盆'],
    },
    'cushion': {
        'display_name': 'Cushion',
        'default_dims': [0.45, 0.45, 0.1],
        'color': [0.5, 0.4, 0.3],
        'material': 'Fabric',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['pillow', 'throw pillow', 'seat cushion'],
        'zh_aliases': ['靠垫', '抱枕', '坐垫'],
    },

    # === 几何基本体 ===
    'ball': {
        'display_name': 'Ball',
        'default_dims': [0.25, 0.25, 0.25],
        'color': [0.8, 0.2, 0.2],
        'material': 'Plastic',
        'category': 'standalone',
        'geometry': 'sphere',
        'aliases': ['sphere', 'orb', 'beach ball', 'football', 'basketball'],
        'zh_aliases': ['球', '圆球', '球体', '皮球'],
    },
    'bottle': {
        'display_name': 'Bottle',
        'default_dims': [0.08, 0.08, 0.25],
        'color': [0.2, 0.6, 0.3],
        'material': 'Glass',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['water bottle', 'wine bottle', 'glass bottle', 'flask'],
        'zh_aliases': ['瓶子', '水瓶', '酒瓶'],
    },
    'bowl': {
        'display_name': 'Bowl',
        'default_dims': [0.2, 0.2, 0.1],
        'color': [0.85, 0.85, 0.85],
        'material': 'Ceramic',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['mixing bowl', 'serving bowl', 'fruit bowl', 'dish'],
        'zh_aliases': ['碗', '碟子', '盘子'],
    },
    'cup': {
        'display_name': 'Cup',
        'default_dims': [0.08, 0.08, 0.12],
        'color': [0.9, 0.9, 0.9],
        'material': 'Ceramic',
        'category': 'standalone',
        'geometry': 'cylinder',
        'aliases': ['mug', 'coffee cup', 'tea cup', 'glass', 'drinking glass'],
        'zh_aliases': ['杯子', '水杯', '茶杯', '咖啡杯'],
    },
    'box': {
        'display_name': 'Box',
        'default_dims': [0.4, 0.3, 0.3],
        'color': [0.6, 0.4, 0.2],
        'material': 'Cardboard',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['cardboard box', 'crate', 'container', 'storage box', 'package'],
        'zh_aliases': ['盒子', '箱子', '纸箱', '收纳盒'],
    },
    'book': {
        'display_name': 'Book',
        'default_dims': [0.15, 0.21, 0.03],
        'color': [0.2, 0.3, 0.7],
        'material': 'Paper',
        'category': 'standalone',
        'geometry': 'cuboid',
        'aliases': ['textbook', 'novel', 'hardcover', 'paperback', 'tome'],
        'zh_aliases': ['书', '书本', '书籍', '教科书'],
    },
}

# ============================================================
# 关键字 -> 类型 查找表（最长匹配优先）
# ============================================================
_KEYWORD_MAP = []
for _type_key, _info in OBJECT_REGISTRY.items():
    for _alias in _info.get('aliases', []):
        _KEYWORD_MAP.append((_alias.lower(), _type_key))
    for _zh in _info.get('zh_aliases', []):
        _KEYWORD_MAP.append((_zh, _type_key))
    _KEYWORD_MAP.append((_type_key.lower(), _type_key))
_KEYWORD_MAP.sort(key=lambda x: -len(x[0]))


def lookup_object(name_lower):
    """根据名称查找类型键。最长匹配优先，避免 'tv' 匹配 'tv stand'。"""
    name_lower = name_lower.strip()
    for keyword, type_key in _KEYWORD_MAP:
        if keyword in name_lower:
            return type_key
    return None


# ============================================================
# 查询辅助函数
# ============================================================
def get_type_info(type_key):
    """获取类型的完整信息字典。"""
    return OBJECT_REGISTRY.get(type_key)


def get_category(type_key):
    """获取类型分类: 'platform', 'satellite', 'standalone'。"""
    info = OBJECT_REGISTRY.get(type_key)
    return info['category'] if info else 'standalone'


def get_default_dims(type_key):
    """获取默认尺寸 [width, depth, height]（复制以避免修改原数据）。"""
    info = OBJECT_REGISTRY.get(type_key)
    return list(info['default_dims']) if info else [1.0, 1.0, 1.0]


def get_color(type_key):
    """获取默认颜色 [R, G, B]。"""
    info = OBJECT_REGISTRY.get(type_key)
    return list(info['color']) if info else [0.5, 0.5, 0.5]


def get_material(type_key):
    """获取默认材质名称。"""
    info = OBJECT_REGISTRY.get(type_key)
    return info['material'] if info else 'Material'


def get_geometry(type_key):
    """获取几何类型: 'composite', 'cuboid', 'cylinder', 'sphere'。"""
    info = OBJECT_REGISTRY.get(type_key)
    return info['geometry'] if info else 'cuboid'


def get_builder(type_key):
    """获取复合构建器名称（仅 composite 类型有效）。"""
    info = OBJECT_REGISTRY.get(type_key)
    return info.get('builder') if info else None


def get_display_name(type_key):
    """获取首字母大写的显示名称。"""
    info = OBJECT_REGISTRY.get(type_key)
    return info['display_name'] if info else type_key.capitalize()


# ============================================================
# 分类集合（从注册表派生，保证一致性）
# ============================================================
PLATFORM_TYPES = {k for k, v in OBJECT_REGISTRY.items() if v['category'] == 'platform'}
SATELLITE_TYPES = {k for k, v in OBJECT_REGISTRY.items() if v['category'] == 'satellite'}
STANDALONE_TYPES = {k for k, v in OBJECT_REGISTRY.items() if v['category'] == 'standalone'}
