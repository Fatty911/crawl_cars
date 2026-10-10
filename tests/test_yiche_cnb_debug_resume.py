import os
from pathlib import Path
import re
import subprocess

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
doc=yaml.safe_load((ROOT/'.cnb.yml').read_text(encoding='utf-8'))
STAGES=[s['script'] for pipelines in doc['main'].values() if isinstance(pipelines,list)
        for pipeline in pipelines for s in pipeline.get('stages',[]) if s.get('name')=='爬取-易车']
assert len(STAGES)==2


def run_actual_args(tmp_path, script, debug, resume):
    output=tmp_path/'actual-args.txt'
    prefix='set -e\npython() { printf "%s\\n" "$@" > "$ARG_OUTPUT"; }\n'
    prefix+='set -- --resume-checkpoint checked\n' if resume else 'set --\n'
    env=dict(os.environ,DEBUG_MODE=str(debug).lower(),ARG_OUTPUT=str(output),RUN_TIME='60',YICHE_REMAINING='30')
    subprocess.run(['sh','-c',prefix+script],env=env,check=True,capture_output=True,text=True)
    return output.read_text().splitlines()


@pytest.mark.parametrize('stage',STAGES)
@pytest.mark.parametrize('debug,resume',[(True,True),(True,False),(False,True),(False,False)])
def test_actual_main_args_obey_resume_and_debug_limits(tmp_path,stage,debug,resume):
    generation='YICHE_EXTRA_ARGS=""'+stage.split('YICHE_EXTRA_ARGS=""',1)[1].split('rc=0',1)[0]
    main=re.search(r'python scripts/crawl_yiche.py --time-limit.*?> /tmp/yiche-main.log 2>&1 \|\| rc=\$\?',stage,re.S).group()
    main=main.replace('> /tmp/yiche-main.log 2>&1','')
    args=run_actual_args(tmp_path,generation+'rc=0\n'+main,debug,resume)
    if resume:
        assert args[args.index('--max-series')+1]=='0'
        assert '--resume-checkpoint' in args
        assert ('--resume-smoke-targets' in args)==debug
        if debug: assert args[args.index('--resume-smoke-targets')+1]=='20'
    elif debug:
        assert args[args.index('--max-series',args.index('--max-series')+1)+1]=='20'


@pytest.mark.parametrize('stage',STAGES)
@pytest.mark.parametrize('debug',[True,False])
def test_actual_fallback_keeps_debug_cap_without_resume(tmp_path,stage,debug):
    fallback='YICHE_FALLBACK_ARGS=""'+stage.split('YICHE_FALLBACK_ARGS=""',1)[1].split('|| echo "易车 重爬仍失败，继续"',1)[0]
    args=run_actual_args(tmp_path,fallback,debug,False)
    positions=[i for i,value in enumerate(args) if value=='--max-series']
    assert args[positions[-1]+1]==('20' if debug else '0')
    assert '--resume-checkpoint' not in args
