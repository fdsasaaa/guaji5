#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import tempfile
import zipfile

MODULE_PATH = Path(__file__).with_name('audit_scheme_semantics.py')
spec = importlib.util.spec_from_file_location('audit_scheme_semantics', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def scheme(body, strategy='定码轮换', play_type='定位胆'):
    text = '\r\n'.join([
        'True', strategy, '软件名称=CXGGJ', f'玩法类型={play_type}', '任选位置=4',
        '倍投类型=1', '倍投计划=1,1,2,3,5,3,2,1', '倍投方案=DM_TEST',
        *body, 'SchemeCreator=', ''
    ])
    return text.encode('gbk')


def assert_has_error(data, phrase):
    result = mod.audit_bytes(data, 'test')
    if not any(phrase in error for error in result['errors']):
        raise AssertionError((phrase, result))


def assert_ok(data):
    result = mod.audit_bytes(data, 'test')
    if result['errors']:
        raise AssertionError(result)


assert_has_error(
    scheme(['投注数字=1 4 7;2 6 0', '定码轮换单组=True']),
    '多个号码组必须拆成多个TXT',
)
assert_has_error(
    scheme(['定码轮换内容=1 4 7;2 6 0', '定码轮换单组=False']),
    '不得使用定码轮换内容',
)
assert_has_error(
    scheme(['投注数字=1,4,7', '定码轮换单组=True']),
    '多个号码组必须拆成多个TXT',
)

for group in ['1 4 7', '2 6 0', '3 7 1', '5 8 9']:
    assert_ok(scheme([f'投注数字={group}', '定码轮换单组=True']))

# Commas in a betting ladder are valid and must not be mistaken for number-group separators.
assert_ok(scheme(['投注数字=1 4 7', '定码轮换单组=True']))

# Verified advanced rotation has its own multi-board field; the ordinary-field guard must not block it.
advanced = scheme(
    ['高级定码轮换内容=1|0 2|1|1;2|3 4|1|1;', '定码轮换单组=False'],
    strategy='高级定码轮换',
    play_type='新龙虎',
)
assert_ok(advanced)

# Numeric filenames must be audited too; filename prefixes are not a bypass.
with tempfile.TemporaryDirectory() as td:
    zpath = Path(td) / 'delivery.zip'
    with zipfile.ZipFile(zpath, 'w') as z:
        z.writestr('方案文件/01_个位_147-定码轮换.txt', scheme(['投注数字=1 4 7;2 6 0', '定码轮换单组=True']))
        z.writestr('GJBTScheme/README.txt', 'not a scheme')
    targets = list(mod.iter_targets(zpath))
    if len(targets) != 1 or '01_个位_147' not in targets[0][0]:
        raise AssertionError(targets)
    assert_has_error(targets[0][1], '多个号码组必须拆成多个TXT')

print('NUMBER_GROUP_FORMAT_GUARD_OK')
