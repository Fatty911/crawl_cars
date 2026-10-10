import copy

import pytest

from scripts.prepare_pages_payload import normalize_publish_row_headers as normalize


@pytest.mark.parametrize('raw,expected', [('●','4.2'),('○ 暂无价格','4.2(选装)'),('待查','待查'),('无','无'),('', '')])
def test_status_does_not_invent_equipment(raw, expected):
    row = {'车型名称':'测试车', '年款':'2026', '数据来源':'懂车帝', 'lcd_dashboard_size_v2_4.2':raw}
    original = copy.deepcopy(row)
    result = normalize(row)
    assert result['液晶仪表尺寸(in)'] == expected
    assert 'lcd_dashboard_size_v2_4.2' not in result
    for key in ('车型名称','年款','数据来源'):
        assert result[key] == row[key]
    assert result['__header_normalization_evidence']['items'][0]['raw_value'] == raw
    assert row == original
    assert normalize(result) == result


def test_values_conflicts_and_non_targets_survive():
    result = normalize({'车内氛围灯':'32色', 'interior_light_v2_64色':'●',
                        'lcd_dashboard_size_v2_7':'●', 'light_special_function_v2_矩阵式':'●',
                        'camera_count_v4_1':'前视', 'foo_v4_bar':'●', 'NOMI Mate 3.0':'选装'})
    assert '32色' in result['车内氛围灯'] and '64色' in result['车内氛围灯']
    assert result['液晶仪表尺寸(in)'] == '7'
    assert result['灯光特色功能'] == '矩阵式'
    assert result['foo_v4_bar'] == '●'
    assert result['NOMI Mate 3.0'] == '选装'
    assert result.get('摄像头数量') != '1'
    assert '前视' in str(result)
