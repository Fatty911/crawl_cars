# Codex Auto Fix Context

- Repository: Fatty911/crawl_cars
- Workflow: 懂车帝爬虫
- Run ID: 28749081024
- Conclusion: failure
- Event: workflow_dispatch
- Head SHA: 18240c947ec83967373af73280d3c10748762bd8

## Task
你正在 GitHub Actions 中作为 Codex 自修复代理运行。
请只在确认是仓库源码、工作流、校验脚本或文档问题时修改代码。
如果日志显示是临时网络、代理订阅不可用、站点短暂限流、GitHub runner 抖动、或者半月完成后的正常跳过，请不要修改文件。

## Repository Rules
- 直接在 main 上修复；禁止 force push。
- 不要启动长时间爬虫；只运行语法校验、workflow 静态校验或很短的 smoke test。
- 修改代码或 workflow 后必须同步 README.md、CHANGELOG.md、HISTORY.md；代理相关还要同步 DOCKER_DEPLOY.md。
- 允许修改的范围：.github/workflows/、custom_scripts/、爬虫脚本、scripts/auto_fix_workflow.py、README/CHANGELOG/HISTORY/AGENTS/部署文档。
- 修复目标是让爬虫 workflow 符合：上午 08:00-12:30，下午 13:00-22:00；长跑自动按 Action 6 小时硬限制和当前时间窗口取更早截止，并保留提交缓冲；每半月完成后跳过。

## Logs
```text
dongchedi-crawl	Set up job	﻿2026-07-05T18:55:43.1930998Z Current runner version: '2.335.1'
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1956902Z ##[group]Runner Image Provisioner
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1957941Z Hosted Compute Agent
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1958574Z Version: 20260624.560
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1959317Z Commit: 925d229a51159bc391ae97e54a2dd1fe20af789d
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1960138Z Build Date: 2026-06-24T18:26:47Z
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1960927Z Worker ID: {574f8351-0fd8-4f8f-87c8-c085a000558f}
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1961822Z Azure Region: eastus2
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1962471Z ##[endgroup]
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1964339Z ##[group]Operating System
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1965083Z Ubuntu
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1965734Z 24.04.4
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1966297Z LTS
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1966840Z ##[endgroup]
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1967542Z ##[group]Runner Image
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1968180Z Image: ubuntu-24.04
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1968803Z Version: 20260628.225.1
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1970340Z Included Software: https://github.com/actions/runner-images/blob/ubuntu24/20260628.225/images/ubuntu/Ubuntu2404-Readme.md
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1972272Z Image Release: https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20260628.225
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1974120Z ##[endgroup]
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1976105Z ##[group]GITHUB_TOKEN Permissions
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1978813Z Contents: write
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1979615Z Metadata: read
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1980251Z ##[endgroup]
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1982709Z Secret source: Actions
dongchedi-crawl	Set up job	2026-07-05T18:55:43.1984299Z Prepare workflow directory
dongchedi-crawl	Set up job	2026-07-05T18:55:43.2379359Z Prepare all required actions
dongchedi-crawl	Set up job	2026-07-05T18:55:43.2417575Z Getting action download info
dongchedi-crawl	Set up job	2026-07-05T18:55:43.5001551Z Download action repository 'actions/checkout@main' (SHA:4f1f4aec02e41874fa0262ea8ff5172d7978ad1e)
dongchedi-crawl	Set up job	2026-07-05T18:55:43.9264040Z Download action repository 'actions/cache@main' (SHA:55cc8345863c7cc4c66a329aec7e433d2d1c52a9)
dongchedi-crawl	Set up job	2026-07-05T18:55:44.1839350Z Download action repository 'actions/setup-python@main' (SHA:ece7cb06caefa5fff74198d8649806c4678c61a1)
dongchedi-crawl	Set up job	2026-07-05T18:55:44.3867917Z Download action repository 'browser-actions/setup-chrome@v2' (SHA:2e1d749697dd1612b833dba4a722266286fbefcd)
dongchedi-crawl	Set up job	2026-07-05T18:55:44.5041878Z Download action repository 'nanasess/setup-chromedriver@v2' (SHA:ef5c64a93512d266b23b80bae95e46a67f30e703)
dongchedi-crawl	Set up job	2026-07-05T18:55:44.6430993Z Download action repository 'actions/upload-artifact@v4' (SHA:ea165f8d65b6e75b540449e92b4886f43607fa02)
dongchedi-crawl	Set up job	2026-07-05T18:55:44.9068537Z Complete job name: dongchedi-crawl
dongchedi-crawl	Run actions/checkout@main	﻿2026-07-05T18:55:45.0252691Z ##[group]Run actions/checkout@main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0254404Z with:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0262356Z   token: ***
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0263463Z   repository: Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0264536Z   ssh-strict: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0265419Z   ssh-user: git
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0266326Z   persist-credentials: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0267304Z   clean: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0268207Z   sparse-checkout-cone-mode: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0269269Z   fetch-depth: 1
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0270143Z   fetch-tags: false
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0271040Z   show-progress: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0271959Z   lfs: false
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0272808Z   submodules: false
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0273924Z   set-safe-directory: true
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0274983Z   allow-unsafe-pr-checkout: false
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0276314Z env:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0277133Z   RUN_TIME: 10800
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0278017Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0278991Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0279987Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0281080Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0282256Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0283443Z   MAX_CARS: 0
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0284333Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0285345Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0286348Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.0287325Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1314849Z Syncing repository: Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1317762Z ##[group]Getting Git version info
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1319404Z Working directory is '/home/runner/work/crawl_cars/crawl_cars'
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1322157Z [command]/usr/bin/git version
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1364722Z git version 2.54.0
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1389247Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1400472Z Temporarily overriding HOME='/home/runner/work/_temp/aa0f82b2-21df-402f-888f-ae9a9f93f110' before making global git config changes
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1405452Z Adding repository directory to the temporary git global config as a safe directory
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1418577Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1464816Z Deleting the contents of '/home/runner/work/crawl_cars/crawl_cars'
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1468737Z ##[group]Determining repository object format
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1471768Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1474685Z ##[group]Initializing the repository
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1477255Z [command]/usr/bin/git init /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1583597Z hint: Using 'master' as the name for the initial branch. This default branch name
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1586214Z hint: will change to "main" in Git 3.0. To configure the initial branch name
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1588569Z hint: to use in all of your new repositories, which will suppress this warning,
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1590437Z hint: call:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1591510Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1592808Z hint: 	git config --global init.defaultBranch <name>
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1594687Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1596308Z hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1598727Z hint: 'development'. The just-created branch can be renamed via this command:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1600474Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1601783Z hint: 	git branch -m <name>
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1603894Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1606167Z hint: Disable this message with "git config set advice.defaultBranchName false"
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1609636Z Initialized empty Git repository in /home/runner/work/crawl_cars/crawl_cars/.git/
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1628161Z [command]/usr/bin/git remote add origin https://github.com/Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1695744Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1698802Z ##[group]Disabling automatic garbage collection
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1701343Z [command]/usr/bin/git config --local gc.auto 0
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1747153Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1750134Z ##[group]Setting up auth
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1752616Z Removing SSH command configuration
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1756848Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.1803706Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2218330Z Removing HTTP extra header
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2228018Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2309614Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2569475Z Removing includeIf entries pointing to credentials config files
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2574462Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2614306Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2877649Z [command]/usr/bin/git config --file /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config http.https://github.com/.extraheader AUTHORIZATION: basic ***
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2925596Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.2966162Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.3010106Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.3047573Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.3076785Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.3078257Z ##[group]Fetching the repository
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.3084715Z [command]/usr/bin/git -c protocol.version=2 fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +18240c947ec83967373af73280d3c10748762bd8:refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5572422Z From https://github.com/Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5575911Z  * [new ref]         18240c947ec83967373af73280d3c10748762bd8 -> origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5616902Z [command]/usr/bin/git branch --list --remote origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5658019Z   origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5667483Z [command]/usr/bin/git rev-parse refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5694705Z 18240c947ec83967373af73280d3c10748762bd8
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5700110Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5701590Z ##[group]Determining the checkout info
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5703603Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5705493Z [command]/usr/bin/git sparse-checkout disable
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5754978Z [command]/usr/bin/git config --local --unset-all extensions.worktreeConfig
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5790552Z ##[group]Checking out the ref
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5794930Z [command]/usr/bin/git checkout --progress --force -B main refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5942551Z Switched to a new branch 'main'
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5945168Z branch 'main' set up to track 'origin/main'.
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.5959158Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.6007346Z [command]/usr/bin/git log -1 --format=%H
dongchedi-crawl	Run actions/checkout@main	2026-07-05T18:55:45.6037932Z 18240c947ec83967373af73280d3c10748762bd8
dongchedi-crawl	Prepare crawl period	﻿2026-07-05T18:55:45.6288733Z ##[group]Run mkdir -p crawl_state
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6289976Z ^[[36;1mmkdir -p crawl_state^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6291075Z ^[[36;1mCN_DAY=$(TZ=Asia/Shanghai date +%d)^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6292338Z ^[[36;1mCN_MONTH=$(TZ=Asia/Shanghai date +%Y%m)^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6293766Z ^[[36;1mif [ $((10#$CN_DAY)) -le 15 ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6294933Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H1"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6295986Z ^[[36;1melse^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6296866Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H2"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6297929Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6299027Z ^[[36;1mDONE_MARKER="crawl_state/dongchedi_${CRAWL_PERIOD}.done"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6300671Z ^[[36;1mCURRENT_PERIOD_FILE="crawl_state/dongchedi_current_period"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6302284Z ^[[36;1mecho "WORKFLOW_START_EPOCH=$(date +%s)" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6303930Z ^[[36;1mecho "CRAWL_PERIOD=$CRAWL_PERIOD" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6305418Z ^[[36;1mecho "DONGCHEDI_DONE_MARKER=$DONE_MARKER" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6307039Z ^[[36;1mecho "crawl_period=$CRAWL_PERIOD" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6308274Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6309100Z ^[[36;1mFORCE_RESTART="false"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6310098Z ^[[36;1mDEBUG_MODE="true"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6311023Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6311892Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6313198Z ^[[36;1m  rm -f "$DONE_MARKER"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6314168Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6314955Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6316279Z ^[[36;1mif [ "$FORCE_RESTART" != "true" ] && [ "$DEBUG_MODE" != "true" ] && [ -f "$DONE_MARKER" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6317977Z ^[[36;1m  echo "$CRAWL_PERIOD 已完成全量懂车帝爬取，本半月不再爬取"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6319218Z ^[[36;1m  echo "SKIP_CRAWL=true" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6320450Z ^[[36;1m  echo "skip=true" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6321809Z ^[[36;1m  exit 0^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6322650Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6323762Z ^[[36;1mecho "INCREMENTAL_MODE=true" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6324931Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6326589Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ] || [ ! -f "$CURRENT_PERIOD_FILE" ] || [ "$(cat "$CURRENT_PERIOD_FILE")" != "$CRAWL_PERIOD" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6328680Z ^[[36;1m  echo "进入新的半月周期 $CRAWL_PERIOD，启用增量模式（保留已有HTML）"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6329914Z ^[[36;1m  rm -f dcd_step2_done^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6330899Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6331860Z ^[[36;1mecho "$CRAWL_PERIOD" > "$CURRENT_PERIOD_FILE"^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6333273Z ^[[36;1mecho "SKIP_CRAWL=false" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6334513Z ^[[36;1mecho "skip=false" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6489126Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6490217Z env:
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6491060Z   RUN_TIME: 10800
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6492021Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6493300Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6494356Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6495494Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6496679Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6497658Z   MAX_CARS: 0
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6498532Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6499520Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6500509Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Prepare crawl period	2026-07-05T18:55:45.6501473Z ##[endgroup]
dongchedi-crawl	Configure crawl window	﻿2026-07-05T18:55:45.6812594Z ##[group]Run if [ "$DEBUG_MODE" = "true" ]; then
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6814119Z ^[[36;1mif [ "$DEBUG_MODE" = "true" ]; then^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6815308Z ^[[36;1m  echo "调试模式：跳过时间窗口限制，每次最多爬30车系"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6816470Z ^[[36;1m  echo "MAX_CARS=30" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6817708Z ^[[36;1m  echo "DEBUG_LIMIT=30" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6818976Z ^[[36;1m  echo "skip=false" >> "$GITHUB_OUTPUT"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6820146Z ^[[36;1melse^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6821194Z ^[[36;1m  python custom_scripts/crawl_budget.py configure^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6822512Z ^[[36;1m  echo "MAX_CARS=0" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6823854Z ^[[36;1m  echo "skip=false" >> "$GITHUB_OUTPUT"^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6824982Z ^[[36;1mfi^[[0m
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6859875Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6860842Z env:
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6861617Z   RUN_TIME: 10800
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6862473Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6863578Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6864600Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6865629Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6866743Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6867722Z   MAX_CARS: 0
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6868566Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6869548Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6870538Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6871556Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6872608Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6873905Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6875211Z   INCREMENTAL_MODE: true
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6876144Z   SKIP_CRAWL: false
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6877016Z   PROFILE_INPUT: auto
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6877908Z   DEBUG_MODE: true
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6878748Z ##[endgroup]
dongchedi-crawl	Configure crawl window	2026-07-05T18:55:45.6946543Z 调试模式：跳过时间窗口限制，每次最多爬30车系
dongchedi-crawl	Calculate delay from trigger time	﻿2026-07-05T18:55:45.7026654Z ##[group]Run echo "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7027995Z ^[[36;1mecho "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"^[[0m
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7029213Z ^[[36;1mecho "delay=0" >> "$GITHUB_OUTPUT"^[[0m
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7065102Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7066076Z env:
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7066866Z   RUN_TIME: 10800
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7067733Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7068697Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7069678Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7070902Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7072016Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7073292Z   MAX_CARS: 30
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7074174Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7075178Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7076174Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7077199Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7078225Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7079383Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7080752Z   INCREMENTAL_MODE: true
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7081684Z   SKIP_CRAWL: false
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7082544Z   DEBUG_LIMIT: 30
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7083665Z ##[endgroup]
dongchedi-crawl	Calculate delay from trigger time	2026-07-05T18:55:45.7151477Z 外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟
dongchedi-crawl	Random delay	﻿2026-07-05T18:55:45.7229275Z ##[group]Run DELAY="0"
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7230248Z ^[[36;1mDELAY="0"^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7231272Z ^[[36;1mif [ "$DELAY" != "0" ] && [ -n "$DELAY" ]; then^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7232750Z ^[[36;1m  echo "Waiting $DELAY seconds ($(($DELAY / 60)) minutes)..."^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7234330Z ^[[36;1m  sleep $DELAY^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7235255Z ^[[36;1melse^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7236092Z ^[[36;1m  echo "跳过延迟"^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7236978Z ^[[36;1mfi^[[0m
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7271824Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7272794Z env:
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7273738Z   RUN_TIME: 10800
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7274668Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7275629Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7276613Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7277661Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7278772Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7279769Z   MAX_CARS: 30
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7280627Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7281663Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7282658Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7283950Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7284987Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7286167Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7287466Z   INCREMENTAL_MODE: true
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7288397Z   SKIP_CRAWL: false
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7289253Z   DEBUG_LIMIT: 30
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7290090Z ##[endgroup]
dongchedi-crawl	Random delay	2026-07-05T18:55:45.7354694Z 跳过延迟
dongchedi-crawl	Restore Dongchedi HTML cache	﻿2026-07-05T18:55:45.7553630Z ##[group]Run actions/cache@main
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7554669Z with:
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7555468Z   path: dongchedi/json
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7556442Z   key: dongchedi-html-202607_H1-28749081024-1
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7557620Z   restore-keys: dongchedi-html-202607_H1-
dongchedi-crawl	Restore Dongchedi HTML cache	
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7558743Z   enableCrossOsArchive: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7559744Z   fail-on-cache-miss: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7560687Z   lookup-only: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7561561Z   save-always: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7562402Z env:
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7563315Z   RUN_TIME: 10800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7564178Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7565114Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7566093Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7567108Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7568187Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7569146Z   MAX_CARS: 30
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7569977Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7570938Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7571939Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7573165Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7574220Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7575359Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7576635Z   INCREMENTAL_MODE: true
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7577543Z   SKIP_CRAWL: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7578368Z   DEBUG_LIMIT: 30
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.7579185Z ##[endgroup]
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:45.9615379Z Cache hit for restore-key: dongchedi-html-202607_H1-28745964478-1
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:46.0480977Z Received 202 of 202 (100.0%), 0.0 MBs/sec
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:46.0481886Z Cache Size: ~0 MB (202 B)
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:46.0513660Z [command]/usr/bin/tar -xf /home/runner/work/_temp/017955cb-d38a-4bba-b0a3-db697f7f79c6/cache.tzst -P -C /home/runner/work/crawl_cars/crawl_cars --use-compress-program unzstd
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:46.0583534Z Cache restored successfully
dongchedi-crawl	Restore Dongchedi HTML cache	2026-07-05T18:55:46.0663985Z Cache restored from key: dongchedi-html-202607_H1-28745964478-1
dongchedi-crawl	Report Dongchedi HTML cache	﻿2026-07-05T18:55:46.0781972Z ##[group]Run mkdir -p dongchedi/json
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0782395Z ^[[36;1mmkdir -p dongchedi/json^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0782857Z ^[[36;1mHTML_COUNT=$(find dongchedi/json -type f -name '*.html' | wc -l)^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0784634Z ^[[36;1mecho "Dongchedi HTML cache files: $HTML_COUNT"^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0816470Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0816804Z env:
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0817052Z   RUN_TIME: 10800
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0817335Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0817637Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0817945Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0818282Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0818637Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0818942Z   MAX_CARS: 30
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0819212Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0819512Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0819811Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0820117Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0820465Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0820833Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0821235Z   INCREMENTAL_MODE: true
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0821533Z   SKIP_CRAWL: false
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0821801Z   DEBUG_LIMIT: 30
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0822079Z ##[endgroup]
dongchedi-crawl	Report Dongchedi HTML cache	2026-07-05T18:55:46.0910094Z Dongchedi HTML cache files: 0
dongchedi-crawl	Run actions/setup-python@main	﻿2026-07-05T18:55:46.1003553Z ##[group]Run actions/setup-python@main
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1003975Z with:
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1004240Z   python-version: 3.12
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1004544Z   check-latest: false
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1007059Z   token: ***
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1007361Z   update-environment: true
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1007686Z   allow-prereleases: false
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1007988Z   freethreaded: false
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1008268Z env:
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1008511Z   RUN_TIME: 10800
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1008791Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1009095Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1009408Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1009738Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1010097Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1010401Z   MAX_CARS: 30
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1010673Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1010974Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1011583Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1011910Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1012267Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1012630Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1013278Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1013592Z   SKIP_CRAWL: false
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1013854Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.1014121Z ##[endgroup]
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.2288454Z ##[group]Installed versions
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.2383336Z Successfully set up CPython (3.12.13)
dongchedi-crawl	Run actions/setup-python@main	2026-07-05T18:55:46.2384474Z ##[endgroup]
dongchedi-crawl	Run browser-actions/setup-chrome@v2	﻿2026-07-05T18:55:46.2553683Z ##[group]Run browser-actions/setup-chrome@v2
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2554341Z with:
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2554759Z   chrome-version: stable
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2555266Z   install-dependencies: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2555803Z   install-chromedriver: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2556297Z   no-sudo: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2556711Z env:
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2557096Z   RUN_TIME: 10800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2557538Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2558018Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2558527Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2559052Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2559623Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2560354Z   MAX_CARS: 30
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2560792Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2561295Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2561804Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2562322Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2562854Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2563759Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2564451Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2564933Z   SKIP_CRAWL: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2565374Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2565922Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2566792Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2567634Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2568407Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2569172Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2569967Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.2570623Z ##[endgroup]
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.3331209Z Setup chrome stable
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.3341932Z Attempting to download chrome stable...
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:46.3733448Z Acquiring chrome stable from https://storage.googleapis.com/chrome-for-testing-public/150.0.7871.46/linux64/chrome-linux64.zip
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:47.2316992Z Installing chrome...
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:47.2395992Z [command]/usr/bin/unzip -o -q /home/runner/work/_temp/89e16dd0-b01e-48d3-853a-a7ee3c454b64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:50.9066886Z Successfully Installed chrome to /opt/hostedtoolcache/setup-chrome/chrome/stable/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:50.9075144Z [command]/opt/hostedtoolcache/setup-chrome/chrome/stable/x64/chrome --version
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:51.2887686Z Google Chrome for Testing 150.0.7871.46 
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T18:55:51.3208265Z Successfully setup chrome 150.0.7871.46
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	﻿2026-07-05T18:55:51.3361503Z ##[group]Run nanasess/setup-chromedriver@v2
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3361902Z with:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3362111Z env:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3362315Z   RUN_TIME: 10800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3362539Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3362806Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3363409Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3363703Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3364002Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3364254Z   MAX_CARS: 30
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3364468Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3364756Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3365003Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3365261Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3365534Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3365842Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3366198Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3366434Z   SKIP_CRAWL: false
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3366656Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3367047Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3367502Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3367955Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3368366Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3368762Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3369169Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.3369521Z ##[endgroup]
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.4019794Z ##setup chromedriver
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:51.4039361Z [command]/home/runner/work/_actions/nanasess/setup-chromedriver/v2/lib/setup-chromedriver.sh  linux64 
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.3324800Z CHROME_VERSION=149
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.3628830Z VERSION=149.0.7827.200
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.3630293Z Downloading https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json...
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.6465743Z Falling back to latest version of ChromeDriver for linux64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.6481823Z VERSION3=149.0.7827
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.8209489Z VERSION=149.0.7827.155
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.9849669Z Installing ChromeDriver 149.0.7827.155 for linux64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:53.9850619Z Downloading https://storage.googleapis.com/chrome-for-testing-public/149.0.7827.155/linux64/chromedriver-linux64.zip...
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:54.2939244Z Installing chromedriver to /usr/local/bin
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:54.3054014Z Chrome version:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:54.3326807Z Google Chrome 149.0.7827.200 
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:54.3333551Z Chromedriver version:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T18:55:54.3370251Z ChromeDriver 149.0.7827.155 (07b52360cc15066f987c910ab34dfbcd4a8778d2-refs/branch-heads/7827@{#3246})
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	﻿2026-07-05T18:55:54.3586137Z ##[group]Run pip install requests beautifulsoup4 selenium lxml PyYAML
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3586712Z ^[[36;1mpip install requests beautifulsoup4 selenium lxml PyYAML^[[0m
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3623973Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3624255Z env:
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3624471Z   RUN_TIME: 10800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3624693Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3624946Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3625193Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3625466Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3625754Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3626008Z   MAX_CARS: 30
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3626220Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3626468Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3626708Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3626970Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3627235Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3627557Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3627951Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3628198Z   SKIP_CRAWL: false
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3628414Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3628696Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3629145Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3629589Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3629989Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3630394Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3630795Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:54.3631141Z ##[endgroup]
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.2385788Z Collecting requests
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.3013862Z   Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.3247123Z Collecting beautifulsoup4
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.3319590Z   Downloading beautifulsoup4-4.15.0-py3-none-any.whl.metadata (3.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.3700799Z Collecting selenium
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.3773256Z   Downloading selenium-4.45.0-py3-none-any.whl.metadata (7.4 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.6373651Z Collecting lxml
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.6450787Z   Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl.metadata (3.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.6876895Z Collecting PyYAML
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.6955605Z   Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.7976623Z Collecting charset_normalizer<4,>=2 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8054519Z   Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8320092Z Collecting idna<4,>=2.5 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8393902Z   Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8635133Z Collecting urllib3<3,>=1.26 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8712278Z   Downloading urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.8930615Z Collecting certifi>=2023.5.7 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9006070Z   Downloading certifi-2026.6.17-py3-none-any.whl.metadata (2.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9214521Z Collecting soupsieve>=1.6.1 (from beautifulsoup4)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9295753Z   Downloading soupsieve-2.8.4-py3-none-any.whl.metadata (4.6 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9504855Z Collecting typing-extensions>=4.0.0 (from beautifulsoup4)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9576360Z   Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9768361Z Collecting trio<1.0,>=0.31.0 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:55.9842570Z   Downloading trio-0.33.0-py3-none-any.whl.metadata (8.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0009999Z Collecting trio-websocket<1.0,>=0.12.2 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0082496Z   Downloading trio_websocket-0.12.2-py3-none-any.whl.metadata (5.1 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0319257Z Collecting websocket-client<2.0,>=1.8.0 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0392845Z   Downloading websocket_client-1.9.0-py3-none-any.whl.metadata (8.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0589475Z Collecting attrs>=23.2.0 (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0665712Z   Downloading attrs-26.1.0-py3-none-any.whl.metadata (8.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0849402Z Collecting sortedcontainers (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.0938619Z   Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl.metadata (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1092780Z Collecting outcome (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1175380Z   Downloading outcome-1.3.0.post0-py2.py3-none-any.whl.metadata (2.6 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1331590Z Collecting sniffio>=1.3.0 (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1410222Z   Downloading sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1585370Z Collecting wsproto>=0.14 (from trio-websocket<1.0,>=0.12.2->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1660820Z   Downloading wsproto-1.3.2-py3-none-any.whl.metadata (5.2 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1825010Z Collecting pysocks!=1.5.7,<2.0,>=1.5.6 (from urllib3[socks]<3.0,>=2.6.3->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.1898573Z   Downloading PySocks-1.7.1-py3-none-any.whl.metadata (13 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2104417Z Collecting h11<1,>=0.16.0 (from wsproto>=0.14->trio-websocket<1.0,>=0.12.2->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2180171Z   Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2301066Z Downloading requests-2.34.2-py3-none-any.whl (73 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2407287Z Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (216 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2604983Z Downloading idna-3.18-py3-none-any.whl (65 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2699898Z Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2800474Z Downloading beautifulsoup4-4.15.0-py3-none-any.whl (109 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.2895387Z Downloading selenium-4.45.0-py3-none-any.whl (9.5 MB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3503201Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 9.5/9.5 MB 175.9 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3580869Z Downloading trio-0.33.0-py3-none-any.whl (510 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3694419Z Downloading trio_websocket-0.12.2-py3-none-any.whl (21 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3787017Z Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3879053Z Downloading PySocks-1.7.1-py3-none-any.whl (16 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.3974338Z Downloading websocket_client-1.9.0-py3-none-any.whl (82 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4067738Z Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl (5.2 MB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4264175Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.2/5.2 MB 293.8 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4337133Z Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (807 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4394874Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 807.9/807.9 kB 164.1 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4467106Z Downloading attrs-26.1.0-py3-none-any.whl (67 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4565379Z Downloading certifi-2026.6.17-py3-none-any.whl (133 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4661822Z Downloading outcome-1.3.0.post0-py2.py3-none-any.whl (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4752798Z Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4848840Z Downloading soupsieve-2.8.4-py3-none-any.whl (37 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.4942098Z Downloading wsproto-1.3.2-py3-none-any.whl (24 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.5035026Z Downloading h11-0.16.0-py3-none-any.whl (37 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.5127687Z Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl (29 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:56.5914401Z Installing collected packages: sortedcontainers, websocket-client, urllib3, typing-extensions, soupsieve, sniffio, PyYAML, pysocks, lxml, idna, h11, charset_normalizer, certifi, attrs, wsproto, requests, outcome, beautifulsoup4, trio, trio-websocket, selenium
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:58.5986731Z 
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T18:55:58.6012378Z Successfully installed PyYAML-6.0.3 attrs-26.1.0 beautifulsoup4-4.15.0 certifi-2026.6.17 charset_normalizer-3.4.7 h11-0.16.0 idna-3.18 lxml-6.1.1 outcome-1.3.0.post0 pysocks-1.7.1 requests-2.34.2 selenium-4.45.0 sniffio-1.3.1 sortedcontainers-2.4.0 soupsieve-2.8.4 trio-0.33.0 trio-websocket-0.12.2 typing-extensions-4.16.0 urllib3-2.7.0 websocket-client-1.9.0 wsproto-1.3.2
dongchedi-crawl	Setup environment	﻿2026-07-05T18:55:58.6680216Z ##[group]Run echo "PYTHONUNBUFFERED=1" >> $GITHUB_ENV
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6680971Z ^[[36;1mecho "PYTHONUNBUFFERED=1" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6682136Z ^[[36;1mecho "MINIMAX_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6682782Z ^[[36;1mecho "ZEN_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6683794Z ^[[36;1mecho "XAI_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6684402Z ^[[36;1mecho "OPENROUTER_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6684923Z ^[[36;1mecho "ACTION_PAT=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6716955Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6717220Z env:
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6717419Z   RUN_TIME: 10800
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6717641Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6717891Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6718144Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6718411Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6718718Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6718982Z   MAX_CARS: 30
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6719229Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6719481Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6719721Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6719984Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6720250Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6720566Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6720913Z   INCREMENTAL_MODE: true
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6721154Z   SKIP_CRAWL: false
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6721368Z   DEBUG_LIMIT: 30
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6721650Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6722085Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6722522Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6723041Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6723451Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6723842Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Setup environment	2026-07-05T18:55:58.6724183Z ##[endgroup]
dongchedi-crawl	Setup proxy if configured	﻿2026-07-05T18:55:58.6810433Z ##[group]Run python custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6811059Z ^[[36;1mpython custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"^[[0m
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6841268Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6841556Z env:
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6841759Z   RUN_TIME: 10800
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6841979Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6842226Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6842470Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6842742Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6843321Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6843594Z   MAX_CARS: 30
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6843809Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6844064Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6844496Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6844756Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6845020Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6845337Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6845712Z   INCREMENTAL_MODE: true
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6845952Z   SKIP_CRAWL: false
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6846164Z   DEBUG_LIMIT: 30
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6846448Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6846883Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6847330Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6847732Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6848123Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6848522Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6848865Z   PYTHONUNBUFFERED: 1
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6849570Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6849979Z   ZEN_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6850461Z   XAI_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6850901Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6851249Z   ACTION_PAT: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6851690Z   PROXY_SUBSCRIPTIONS: ***
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.6851941Z ##[endgroup]
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.9487297Z Traceback (most recent call last):
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.9494976Z   File "/home/runner/work/crawl_cars/crawl_cars/custom_scripts/setup_proxy_runtime.py", line 27, in <module>
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.9496088Z     from generate_clash_config import ClashConfigGenerator, redact_url
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.9496864Z ModuleNotFoundError: No module named 'generate_clash_config'
dongchedi-crawl	Setup proxy if configured	2026-07-05T18:55:58.9696892Z ##[error]Process completed with exit code 1.
dongchedi-crawl	Disable proxy for GitHub artifact upload	﻿2026-07-05T18:55:58.9789127Z ##[group]Run {
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9789389Z ^[[36;1m{^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9789604Z ^[[36;1m  echo "HTTP_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9789862Z ^[[36;1m  echo "HTTPS_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9790135Z ^[[36;1m  echo "ALL_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9790382Z ^[[36;1m  echo "http_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9790642Z ^[[36;1m  echo "https_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9790901Z ^[[36;1m  echo "all_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9791150Z ^[[36;1m} >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9822814Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9823219Z env:
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9823422Z   RUN_TIME: 10800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9823657Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9823900Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9824151Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9824414Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9824700Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9824947Z   MAX_CARS: 30
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9825162Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9825449Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9825692Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9825945Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9826222Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9826530Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9826884Z   INCREMENTAL_MODE: true
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9827121Z   SKIP_CRAWL: false
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9827341Z   DEBUG_LIMIT: 30
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9827618Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9828070Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9828502Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9828895Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9829287Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9829683Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9830024Z   PYTHONUNBUFFERED: 1
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9830790Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9831210Z   ZEN_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9831706Z   XAI_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9832306Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9832671Z   ACTION_PAT: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-07-05T18:55:58.9833074Z ##[endgroup]
dongchedi-crawl	Upload error log	﻿2026-07-05T18:55:58.9952668Z Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true environment variable. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9954327Z ##[group]Run actions/upload-artifact@v4
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9954617Z with:
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9954812Z   name: error-log
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9955050Z   path: step1_error.log
dongchedi-crawl	Upload error log	step2_error.log
dongchedi-crawl	Upload error log	
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9955336Z   if-no-files-found: ignore
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9955585Z   retention-days: 7
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9955801Z   compression-level: 6
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9956030Z   overwrite: false
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9956254Z   include-hidden-files: false
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9956496Z env:
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9956687Z   RUN_TIME: 10800
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9956901Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9957134Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9957402Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9957665Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9957944Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9958190Z   MAX_CARS: 30
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9958394Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9958636Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9958871Z   DCD_GET_TIMEOUT_SECONDS: 45
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9959122Z   WORKFLOW_START_EPOCH: 1783277745
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9959381Z   CRAWL_PERIOD: 202607_H1
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9959690Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202607_H1.done
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9960037Z   INCREMENTAL_MODE: true
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9960282Z   SKIP_CRAWL: false
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9960492Z   DEBUG_LIMIT: 30
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9960769Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9961214Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9961641Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9962037Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9962427Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9962821Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9963440Z   PYTHONUNBUFFERED: 1
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9964168Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9964593Z   ZEN_API_KEY: ***
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9965073Z   XAI_API_KEY: ***
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9965486Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9965838Z   ACTION_PAT: ***
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9966053Z   HTTP_PROXY: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9966263Z   HTTPS_PROXY: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9966459Z   ALL_PROXY: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9966656Z   http_proxy: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9966847Z   https_proxy: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9967047Z   all_proxy: 
dongchedi-crawl	Upload error log	2026-07-05T18:55:58.9967244Z ##[endgroup]
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1567318Z (node:2463) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead.
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1568626Z (Use `node --trace-deprecation ...` to show where the warning was created)
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1605498Z Multiple search paths detected. Calculating the least common ancestor of all paths
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1608267Z The least common ancestor is /home/runner/work/crawl_cars/crawl_cars. This will be the root directory of the artifact
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1609616Z No files were found with the provided path: step1_error.log
dongchedi-crawl	Upload error log	2026-07-05T18:55:59.1610447Z step2_error.log. No artifacts will be uploaded.
dongchedi-crawl	Post Run actions/checkout@main	﻿2026-07-05T18:55:59.1924688Z Post job cleanup.
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2811396Z [command]/usr/bin/git version
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2853389Z git version 2.54.0
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2893889Z Temporarily overriding HOME='/home/runner/work/_temp/b3226c1f-ebda-4d55-972a-d883cceccf47' before making global git config changes
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2895886Z Adding repository directory to the temporary git global config as a safe directory
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2910706Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2944748Z Removing SSH command configuration
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.2953533Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3001377Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3259034Z Removing HTTP extra header
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3265681Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3310199Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3562508Z Removing includeIf entries pointing to credentials config files
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3573288Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3605574Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3606693Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3607726Z includeif.gitdir:/github/workspace/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3608658Z includeif.gitdir:/github/workspace/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3616416Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3644601Z /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3659764Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3704402Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3738129Z /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3748765Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3789409Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3817852Z /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3826527Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3864985Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3892011Z /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3901861Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.3938462Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
dongchedi-crawl	Post Run actions/checkout@main	2026-07-05T18:55:59.4180465Z Removing credentials config '/home/runner/work/_temp/git-credentials-4df9552e-a3ce-497a-9435-a980ac678cfa.config'
dongchedi-crawl	Complete job	﻿2026-07-05T18:55:59.4319554Z Cleaning up orphan processes
dongchedi-crawl	Complete job	2026-07-05T18:55:59.4618682Z ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/upload-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

```
