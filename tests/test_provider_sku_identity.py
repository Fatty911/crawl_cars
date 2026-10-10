import copy

import pytest

from scripts.prepare_pages_payload import _model_ids, _model_id_fields
from scripts.prepare_pages_payload import _strong_existing_multi_variant


@pytest.mark.parametrize('field,value', [
    ('关联组件ID','visible-f-v3:ab77904cd'),('相关车型ID','2026款'),
    ('车系ID','77904'),('跨源归并ID','visible-f-v3:77904'),
    ('车型ID','prefix77904suffix'),('车型ID','123,456'),('车型ID','0')])
def test_non_primary_or_partial_ids_never_become_identity(field,value):
    assert not _model_ids({'数据来源':'易车',field:value})


def test_provider_namespaces_do_not_collide_and_real_ids_match():
    ah={'数据来源':'汽车之家','车型ID':'77904'}
    yc={'数据来源':'易车','车型ID':'77904'}
    assert _model_ids(ah)=={'汽车之家|77904'}
    assert not (_model_ids(ah)&_model_ids(yc))
    assert _model_ids(ah)&_model_ids({'数据来源':'汽车之家','车款ID':'77904'})


def test_multisource_generic_stays_unknown_and_original_evidence_survives():
    row={'数据来源':'汽车之家+懂车帝','车款ID':'77904'}
    before=copy.deepcopy(row)
    assert not _model_ids(row)
    assert _model_id_fields(row)=={'车款ID':'77904'}
    assert row==before


def test_explicit_provider_evidence_and_conflicting_prefix():
    assert _model_ids({'数据来源':'汽车之家+易车','易车车型ID':'77904'})=={'易车|77904'}
    assert _model_ids({'车型ID':'汽车之家:77904'})=={'汽车之家|77904'}
    assert not _model_ids({'易车车型ID':'汽车之家:77904'})
    assert _model_ids({'数据来源':'懂车帝','车型ID':'7'})=={'懂车帝|7'}


def test_existing_multi_feature_defer_requires_complete_matching_variant():
    row={'车型名称':'2026款 Elite 后驱增程版','能源类型':'增程式',
         '驱动形式':'后置后驱','座位数(个)':'5','电池能量(kWh)':'39.05'}
    assert _strong_existing_multi_variant(row,dict(row))
    for key,value in [('电池能量(kWh)',''),('电池能量(kWh)','52'),
                      ('座位数(个)','6'),('驱动形式','四驱'),
                      ('能源类型','纯电动'),('车型名称','2026款 Pro 后驱增程版')]:
        assert not _strong_existing_multi_variant(row,dict(row,**{key:value})),key
